"""Video judge: scores a quick DRAFT render before the final render is spent. Free (local GPU / CPU).

Attention checks (code): motion in the first 2 s, speech start, dead/frozen frames, cut rhythm, loudness, length.
Viewer check (Claude Haiku, or local Qwen2.5-VL): looks at 1 fps frames + transcript, scores hook and line-to-footage match.
Pass = every attention check passes AND the viewer scores meet config video_judge.min.
Thresholds are starting points; tune them with real Meta results (hook rate, ThruPlay, CTR, cost per lead).
"""
import re
import subprocess
import wave
from pathlib import Path

import cv2
import numpy as np

from common import ffmpeg_bin, log, read_json, write_json


def _frames(cfg, video, fps, width, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.jpg"):
        f.unlink()
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-vf", f"fps={fps},scale={width}:-2", "-q:v", "4", str(out_dir / "%04d.jpg")], check=True)
    return sorted(out_dir.glob("*.jpg"))


def _loudness(cfg, video):
    r = subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-i", str(video), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, errors="ignore")
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", r.stderr)
    return float(m[-1]) if m else None


def _speech_start(wav_path, thresh_db=-35):
    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = sr // 50
    for i in range(0, len(x) - hop, hop):
        if 20 * np.log10(np.sqrt(np.mean(x[i:i + hop] ** 2)) + 1e-9) > thresh_db:
            return i / sr
    return None


def attention_checks(cfg, run, video):
    vj = cfg["video_judge"]
    tl = read_json(run / "timeline.json")
    frames = _frames(cfg, video, 8, 160, run / "judge_frames")
    gray = [cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
    diffs = [float(np.abs(gray[i] - gray[i - 1]).mean()) for i in range(1, len(gray))]
    luma = [float(g.mean()) for g in gray]
    hook_motion = float(np.mean(diffs[:16])) if diffs else 0.0                 # first 2 s at 8 fps
    dead = 0
    run_len = 0
    for dv, lv in zip(diffs, luma[1:]):
        run_len = run_len + 1 if (dv < 0.25 or lv < 10) else 0
        dead = max(dead, run_len)
    dead_s = dead / 8
    dur = tl["total_duration_seconds"]
    cuts_per_10s = len(tl["timeline"]) / dur * 10
    speech = _speech_start(run / tl.get("voiceover_audio", "voiceover.wav"))
    lufs = _loudness(cfg, video)
    lo, hi = vj["duration_s"]
    checks = {
        "hook_motion": (round(hook_motion, 2), hook_motion >= vj["min_hook_motion"]),
        "speech_start_s": (speech, speech is not None and speech <= vj["max_speech_start_s"]),
        "longest_dead_s": (round(dead_s, 2), dead_s <= vj["max_dead_s"]),
        "cuts_per_10s": (round(cuts_per_10s, 2), vj["cuts_per_10s"][0] <= cuts_per_10s <= vj["cuts_per_10s"][1]),
        "loudness_lufs": (lufs, lufs is None or abs(lufs - vj["target_lufs"]) <= 3),
        "duration_s": (round(dur, 1), lo - 1 <= dur <= hi + 2),
    }
    return checks


VIEWER_SYSTEM = """You are a scrolling Instagram user in India (30-50, Hyderabad professional or NRI) who might want a weekend forest home.
You also think like a senior performance-ad editor. Judge this Reel draft honestly from frames and its voiceover."""


def viewer_score(cfg, run, video):
    tl = read_json(run / "timeline.json")
    frames = _frames(cfg, video, 1, 360, run / "judge_frames_1fps")[:40]
    said = " | ".join(f"{v['start']:.0f}s: {v['text']}" for v in tl["voiceover"])
    prompt = f"""Frames above are 1 per second of a {tl['total_duration_seconds']:.0f} s Reel draft. Voiceover with start times:
{said}

Score 0-10:
- hook: would the first 2 seconds stop your scroll?
- match: does what you see match what is being said, line by line?
- overall: would you watch to the end and consider tapping the CTA?
Return JSON: {{"hook": <0-10>, "match": <0-10>, "overall": <0-10>, "weakest_moment_s": <int>, "note": "<one line>"}}"""
    if cfg["video_judge"].get("viewer", "claude") == "local":
        from local_models import vlm_json
        return vlm_json(cfg, VIEWER_SYSTEM, [(f"t={i}s", f) for i, f in enumerate(frames)], prompt, max_new_tokens=400)
    from common import ask_claude_json, image_block            # Claude Haiku: ~38 small frames, about $0.001
    content = []
    for i, f in enumerate(frames):
        content += [{"type": "text", "text": f"t={i}s"}, image_block(Path(f).read_bytes())]
    content.append({"type": "text", "text": prompt})
    return ask_claude_json(cfg, "judge_model", VIEWER_SYSTEM, content)


def judge_video(cfg, run, video):
    run = Path(run)
    vj = cfg["video_judge"]
    checks = attention_checks(cfg, run, video)
    fails = [f"{k}={v[0]}" for k, v in checks.items() if not v[1]]
    viewer = None
    if vj.get("use_vlm", True):
        try:
            viewer = viewer_score(cfg, run, video)
            for k, m in vj["min"].items():
                if float(viewer.get(k, 0)) < m:
                    fails.append(f"viewer {k} {viewer.get(k)} < {m}")
        except Exception as e:                       # no GPU / model missing: attention checks still gate
            log("video_judge", f"viewer model unavailable ({e}); using attention checks only")
    score = round(sum(v[1] for v in checks.values()) / len(checks) * 50 +
                  (sum(float(viewer.get(k, 0)) for k in ("hook", "match", "overall")) / 30 * 50 if viewer else 0), 1)
    res = {"passed": not fails, "score": score, "fails": fails,
           "checks": {k: {"value": v[0], "ok": v[1]} for k, v in checks.items()}, "viewer": viewer}
    write_json(run / "video_judge.json", res)
    return res
