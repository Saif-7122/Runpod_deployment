"""Shared helpers: config, paths, Claude calls, ffmpeg binary, JSON I/O."""
import base64
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def log(tag, msg):
    print(f"[{datetime.now():%H:%M:%S}] [{tag}] {msg}", file=sys.stderr, flush=True)


def _deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path=None):
    path = Path(path or os.environ.get("CE_CONFIG", ROOT / "config.yaml"))
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # profile overrides, e.g. CE_PROFILE=pc -> profiles/pc.yaml (deep-merged over config.yaml)
    prof = os.environ.get("CE_PROFILE")
    if prof:
        with open(ROOT / "profiles" / f"{prof}.yaml", "r", encoding="utf-8") as f:
            _deep_merge(cfg, yaml.safe_load(f) or {})
    if os.environ.get("CE_CODEC"):
        cfg["rendering"]["video_codec"] = os.environ["CE_CODEC"]
    if os.environ.get("CE_HW_DECODE"):
        cfg["rendering"]["hw_decode"] = os.environ["CE_HW_DECODE"] == "1"
    if os.environ.get("CE_FONTS_DIR"):
        cfg["captions"]["fonts_dir"] = os.environ["CE_FONTS_DIR"]
    ws = os.environ.get("CE_WORKSPACE") or cfg.get("workspace") or "./workspace"
    ws = Path(ws)
    if not ws.is_absolute():
        ws = (ROOT / ws).resolve()
    cfg["_paths"] = {
        "workspace": ws,
        "catalog": ws / "catalog",
        "catalog_file": ws / "catalog" / "catalog.json",
        "frames": ws / "catalog" / "frames",
        "clips": ws / "cache" / "clips",
        "proxies": ws / "cache" / "proxies",
        "runs": ws / "runs",
    }
    for key in ("catalog", "frames", "clips", "proxies", "runs"):
        cfg["_paths"][key].mkdir(parents=True, exist_ok=True)
    return cfg


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def new_run_id(label="run"):
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:30] or "run"
    return f"{datetime.now():%Y%m%d-%H%M%S}-{slug}-{os.urandom(2).hex()}"


def ffmpeg_bin(cfg=None):
    """System ffmpeg if present, else the imageio-ffmpeg binary (local testing)."""
    explicit = os.environ.get("FFMPEG_BIN") or (cfg or {}).get("rendering", {}).get("ffmpeg_bin")
    if explicit:
        return explicit
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError("ffmpeg not found. Install it or `pip install imageio-ffmpeg`.")


# ---------------------------------------------------------------- Claude

_client = None


def claude_client():
    global _client
    if _client is None:
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set (put it in .env).")
        headers = {}
        if os.environ.get("ANTHROPIC_WORKSPACE_ID"):      # needed for keys not scoped to a workspace
            headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
        _client = anthropic.Anthropic(max_retries=5, default_headers=headers or None)
    return _client


def image_block(jpeg_bytes):
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg",
                   "data": base64.b64encode(jpeg_bytes).decode("ascii")},
    }


def extract_json(text):
    """Parse the first JSON object or array in a model reply."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError(f"No JSON in model reply: {text[:200]}")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1])


import threading
_usage_lock = threading.Lock()
USAGE = {}          # model -> token counts, for cost reporting per run / batch


def usage_snapshot():
    with _usage_lock:
        return json.loads(json.dumps(USAGE))


# $ per million tokens: input, output, cache read, cache write (list prices, Oct 2026; edit in config.pricing)
DEFAULT_PRICES = {"claude-opus-5-5": [4.0, 20.0, 0.20, 5.0], "claude-sonnet-5-5": [2.0, 10.0, 0.20, 2.5],
                  "claude-haiku-5-5": [0.10, 0.50, 0.01, 0.125]}


def usage_cost(cfg=None, usage=None):
    """Dollar cost of the Claude calls made so far in this process."""
    prices = {**DEFAULT_PRICES, **((cfg or {}).get("pricing") or {})}
    total = 0.0
    for model, u in (usage or usage_snapshot()).items():
        pi, po, pr, pw = prices.get(model, DEFAULT_PRICES["claude-opus-5-5"])
        total += (u["input"] * pi + u["output"] * po + u["cache_read"] * pr + u["cache_write"] * pw) / 1e6
    return round(total, 4)


class BudgetExceeded(RuntimeError):
    pass


def check_budget(cfg):
    cap = (cfg.get("batch") or {}).get("max_claude_usd")
    if cap and usage_cost(cfg) >= cap:
        raise BudgetExceeded(f"Claude spend ${usage_cost(cfg):.2f} reached the batch cap ${cap:.2f}")


def _record_usage(model, u):
    with _usage_lock:
        m = USAGE.setdefault(model, {"calls": 0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
        m["calls"] += 1
        m["input"] += getattr(u, "input_tokens", 0) or 0
        m["output"] += getattr(u, "output_tokens", 0) or 0
        m["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        m["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0


def ask_claude_json(cfg, model_key, system, content, max_tokens=None, cache_system=True, temperature=None, schema=None):
    """One Claude call that returns parsed JSON.

    Current models (Opus 5.5 / Sonnet 5.5) always think before answering; `max_tokens` must cover thinking
    + answer, so we stream with a generous ceiling (you pay only for tokens actually produced) and set the
    thinking depth per task with output_config.effort (config models.effort.<model_key>).
    `temperature` is rejected by these models and is ignored unless models.send_temperature is true.
    """
    if cfg.get("llm_provider") == "local" and model_key in ("director_model", "judge_model"):
        from local_models import llm_json            # free local Qwen3 on the GPU, no Claude spend
        last_err = None
        for attempt in range(2):
            try:
                return llm_json(cfg, system, content, schema=schema)
            except (ValueError, json.JSONDecodeError) as e:
                last_err = e
        raise RuntimeError(f"local LLM returned invalid JSON twice: {last_err}")
    model = cfg["models"][model_key]
    effort = cfg["models"].get("effort", {}).get(model_key)
    max_tokens = max_tokens or cfg["models"].get("max_tokens", 64000)
    sys_block = [{"type": "text", "text": system}]
    if cache_system:
        sys_block[0]["cache_control"] = {"type": "ephemeral"}
    messages = [{"role": "user", "content": content}]
    extra = {}
    if temperature is not None and cfg["models"].get("send_temperature"):
        extra["temperature"] = temperature
    if effort:
        extra["output_config"] = {"effort": effort}
    last_err = None
    check_budget(cfg)
    for attempt in range(2):
        with claude_client().messages.stream(model=model, max_tokens=max_tokens, system=sys_block,
                                             messages=messages, **extra) as stream:
            resp = stream.get_final_message()
        _record_usage(model, resp.usage)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined the request ({getattr(resp, 'stop_details', None)})")
        text = "".join(b.text for b in resp.content if b.type == "text")
        if resp.stop_reason == "max_tokens" and not text:
            raise RuntimeError(f"Claude used the whole {max_tokens}-token budget thinking; raise models.max_tokens "
                               f"or lower models.effort.{model_key}")
        try:
            return extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            # append-only retry: keep the model's full answer (incl. thinking blocks) and ask for JSON only
            messages = messages + [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": "That was not valid JSON. Reply with only the JSON object."},
            ]
            time.sleep(1)
    raise RuntimeError(f"Claude returned invalid JSON twice: {last_err}")
