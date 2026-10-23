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


def load_config(path=None):
    path = Path(path or os.environ.get("CE_CONFIG", ROOT / "config.yaml"))
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
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


def ask_claude_json(cfg, model_key, system, content, max_tokens=4000, cache_system=True):
    """Send one message and return parsed JSON. Retries once on unparseable output."""
    model = cfg["models"][model_key]
    sys_block = [{"type": "text", "text": system}]
    if cache_system:
        sys_block[0]["cache_control"] = {"type": "ephemeral"}
    messages = [{"role": "user", "content": content}]
    last_err = None
    for attempt in range(2):
        resp = claude_client().messages.create(
            model=model, max_tokens=max_tokens, system=sys_block, messages=messages)
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            return extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "That was not valid JSON. Reply with only the JSON."},
            ]
            time.sleep(1)
    raise RuntimeError(f"Claude returned invalid JSON twice: {last_err}")
