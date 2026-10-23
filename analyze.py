"""Clip analysis: watch every raw clip once and cut it into approved segments.

Stage A  shot splitting       (colour-histogram cut detection on 4 fps frames)
Stage B  technical scoring    (sharpness, exposure, shake / whip-pan every 0.25 s; OpenCV)
Stage C  visual understanding (Claude looks at 1 fps timestamped frames)
Stage D  decision             (approved / rejected with a reason) -> catalog.json + summary.md

Usage:
  python analyze.py --drive                 # all clips under drive.raw_folder_id in config.yaml
  python analyze.py --local D:/footage      # a local folder (subfolders = projects)
  python analyze.py --drive --force         # re-analyse everything
  python analyze.py --drive --limit 5       # quick test on 5 clips
"""
import argparse
import hashlib
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from common import ask_claude_json, ffmpeg_bin, image_block, load_config, log, read_json, write_json

ANALYSIS_VERSION = 3
ANALYSIS_FPS = 4          # technical scoring rate
VISION_FPS = 1            # frames shown to Claude
_lock = threading.Lock()


# ------------------------------------------------------------------ sources

def collect_sources(cfg, args):
    if args.local:
        root = Path(args.local)
        items = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"):
                rel = p.relative_to(root)
                project = rel.parts[0] if len(rel.parts) > 1 else root.name
                st = p.stat()
                items.append({
                    "id": "local-" + hashlib.sha1(str(p.resolve()).encode()).hexdigest()[:16],
                    "name": p.name, "project": project, "drive_path": str(rel).replace("\\", "/"),
                    "size": st.st_size, "modifiedTime": str(int(st.st_mtime)), "_local": str(p),
                })
        return items
    import drive
    folder = cfg["drive"]["raw_folder_id"]
    return drive.list_videos(folder)


def fetch_clip(cfg, item):
    if item.get("_local"):
        return Path(item["_local"])
    import drive
    ext = Path(item["name"]).suffix.lower() or ".mp4"
    dest = cfg["_paths"]["clips"] / f"{item['id']}{ext}"
    if not dest.exists():
        log("analyze", f"downloading {item['name']} ({int(item.get('size', 0)) / 1e6:.0f} MB)")
        drive.download(item["id"], dest)
    return dest


# ------------------------------------------------------------------ stage 0: decode once

def probe(path):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"fps": round(fps, 3), "duration_s": round(n / fps, 2) if fps else 0.0, "width": w, "height": h}


def has_audio_stream(cfg, path):
    r = subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, errors="ignore")
    return " Audio:" in r.stderr


def extract_frames(cfg, clip_path, out_dir, proxy_path=None):
    """One decode pass: 4 fps analysis frames, 1 fps vision frames, optional 9:16-friendly proxy."""
    a_dir, v_dir = out_dir / "a", out_dir / "v"
    for d in (a_dir, v_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    rc = cfg["rendering"]
    graph = (f"[0:v]split={3 if proxy_path else 2}[a][b]{'[c]' if proxy_path else ''};"
             f"[a]fps={ANALYSIS_FPS},scale=480:-2,format=yuvj420p[a1];"
             f"[b]fps={VISION_FPS},scale={cfg['analysis']['vision_frame_width']}:-2,format=yuvj420p[b1]")
    cmd = [ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip_path),
           "-filter_complex", graph if not proxy_path else graph +
           ";[c]scale='if(gt(iw,ih),-2,1080)':'if(gt(iw,ih),1920,-2)',fps=30,format=yuv420p[c1]",
           "-map", "[a1]", "-q:v", "5", str(a_dir / "%05d.jpg"),
           "-map", "[b1]", "-q:v", "3", str(v_dir / "%05d.jpg")]
    if proxy_path:
        cmd += ["-map", "[c1]", "-map", "0:a:0?", *encoder_args(rc, proxy=True), "-g", "15",
                "-c:a", "aac", "-b:a", "160k", str(proxy_path)]
    subprocess.run(cmd, check=True)
    return sorted(a_dir.glob("*.jpg")), sorted(v_dir.glob("*.jpg"))


def encoder_args(rc, proxy=False):
    cap = ["-maxrate", "6M", "-bufsize", "12M"] if proxy else []   # proxies: ~45 MB per minute max
    if rc["video_codec"] == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4" if proxy else rc.get("nvenc_preset", "p5"),
                "-cq", "24" if proxy else str(rc.get("cq", 21)), "-b:v", "0", *cap]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23" if proxy else str(rc.get("crf", 20)), *cap]


# ------------------------------------------------------------------ stage A + B: technical

def technical_scan(frames, th):
    step = 1.0 / ANALYSIS_FPS
    rows, prev_gray, prev_hist, prev_shift = [], None, None, np.zeros(2)
    window = None
    for i, fp in enumerate(frames):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        row = {
            "t": round(i * step, 2),
            "sharp": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            "bright": float(gray.mean()),
            "clipped": float((gray > 250).mean()),
            "cut": False, "speed": 0.0, "jerk": 0.0,
        }
        if prev_gray is not None:
            if window is None:
                window = cv2.createHanningWindow((w, h), cv2.CV_32F)
            (dx, dy), response = cv2.phaseCorrelate(np.float32(prev_gray), np.float32(gray), window)
            shift = np.array([dx, dy]) / w                      # fraction of frame width per step
            row["speed"] = float(np.hypot(*shift))
            row["jerk"] = float(np.hypot(*(shift - prev_shift)))
            diff = float(cv2.absdiff(prev_gray, gray).mean())
            row["cut"] = (cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL) < th["cut_hist_correl"]
                          or (response < th["cut_track_response"] and diff > th["cut_frame_diff"]))
            if row["cut"]:
                row["speed"] = row["jerk"] = 0.0                  # a cut is not camera motion
                shift = np.zeros(2)
            prev_shift = shift
        prev_gray, prev_hist = gray, hist
        rows.append(row)
    if not rows:
        return rows

    med_sharp = float(np.median([r["sharp"] for r in rows])) or 1.0
    def rolling_median(vals, k):
        vals, half = np.asarray(vals), k // 2
        return np.array([np.median(vals[max(0, i - half): i + half + 1]) for i in range(len(vals))])

    # medians ignore single-frame spikes (a bird, a compression glitch); sustained motion still counts
    shake = rolling_median([r["jerk"] for r in rows], ANALYSIS_FPS + 1)          # ~1 s window
    speed = rolling_median([r["speed"] for r in rows], 3)                       # ~0.75 s window
    for r, s, sp in zip(rows, shake, speed):
        r["speed"] = float(sp)
        reasons = []
        if r["sharp"] < th["sharp_rel"] * med_sharp or r["sharp"] < th["sharp_abs"]:
            reasons.append("blurry")
        if r["bright"] < th["dark_mean"]:
            reasons.append("too dark")
        if r["clipped"] > th["clipped_frac"]:
            reasons.append("blown out")
        if r["speed"] > th["whip_speed"]:
            reasons.append("whip-pan")
        if s > th["shake_jerk"]:
            reasons.append("shaky")
        r["shake"] = float(s)
        r["bad"] = reasons
    return rows


def candidate_segments(rows, duration, th):
    """Runs of good samples inside one shot, trimmed at record start/stop."""
    step = 1.0 / ANALYSIS_FPS
    trim = th["edge_trim_s"]
    segs, rejects, cur, bad_run = [], [], None, None

    def close_bad(end_t):
        nonlocal bad_run
        if bad_run and end_t - bad_run[0] >= step:
            rejects.append({"in": bad_run[0], "out": round(end_t, 2), "status": "rejected",
                            "reject_reason": ", ".join(sorted(bad_run[1]))})
        bad_run = None

    for r in rows:
        t = r["t"]
        good = not r["bad"] and trim <= t <= duration - trim - step
        if r["cut"] and cur:
            segs.append(cur)
            cur = None
        if good:
            close_bad(t)
            if cur is None:
                cur = [t, t + step]
            else:
                cur[1] = t + step
        else:
            if cur:
                segs.append(cur)
                cur = None
            if r["bad"]:
                if bad_run is None:
                    bad_run = [t, set()]
                bad_run[1].update(r["bad"])
    if cur:
        segs.append(cur)
    close_bad(rows[-1]["t"] + step)

    out = []
    for a, b in segs:
        if b - a < th["min_segment_s"]:
            continue
        while b - a > th["max_segment_s"] + th["min_segment_s"]:     # split very long runs
            out.append([a, a + th["max_segment_s"]])
            a += th["max_segment_s"]
        out.append([a, b])
    return [{"in": round(a, 2), "out": round(b, 2)} for a, b in out], rejects


# ------------------------------------------------------------------ stage B2: the clip's own audio

def extract_audio(cfg, clip_path, wav_path):
    r = subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip_path),
                        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path)],
                       capture_output=True, text=True, errors="ignore")
    return r.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 1000


def speech_phrases(wav_path, au):
    """Split audio into phrases at silences (100 ms RMS frames). Returns [(in, out)] and mean dB."""
    import wave
    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = sr // 10
    n = len(x) // hop
    if n == 0:
        return [], -100.0
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    loud = db > au["silence_db"]
    phrases, start, quiet = [], None, 0
    for i, on in enumerate(loud):
        if on:
            start = i if start is None else start
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * 0.1 >= au["min_gap_s"]:
                phrases.append((start * 0.1, (i - quiet + 1) * 0.1))
                start, quiet = None, 0
    if start is not None:
        phrases.append((start * 0.1, n * 0.1))
    # speech under music has no silences: split long phrases at their quietest 100 ms points
    limit = au["max_stt_chunk_s"]
    split = []
    for a, b in phrases:
        while b - a > limit:
            lo, hi = int((a + limit * 0.6) * 10), int((a + limit) * 10)
            cut = (lo + int(np.argmin(db[lo:hi]))) / 10 if hi > lo else a + limit
            split.append((a, cut))
            a = cut
        split.append((a, b))
    phrases = [(round(a, 2), round(b, 2)) for a, b in split if b - a >= 0.4]
    return phrases, float(db.mean())


def transcribe(cfg, wav_path, a, b, tmp):
    """Sarvam speech-to-text for one stretch of audio (< 30 s)."""
    import os
    import requests
    au = cfg["audio"]
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.2f}",
                    "-t", f"{b - a:.2f}", "-i", str(wav_path), "-c:a", "pcm_s16le", str(tmp)], check=True)
    with open(tmp, "rb") as f:
        r = requests.post(au["stt_url"], headers={"api-subscription-key": os.environ["SARVAM_API_KEY"]},
                          files={"file": ("a.wav", f, "audio/wav")},
                          data={"model": au["stt_model"], "language_code": "unknown"}, timeout=120)
    r.raise_for_status()
    return r.json().get("transcript", "").strip()


def audio_scan(cfg, clip, workdir):
    """Find what is said in the clip. Returns a list of {in, out, text} lines, or [] for music/ambient/silence."""
    au = cfg["audio"]
    workdir.mkdir(parents=True, exist_ok=True)
    wav = workdir / "audio16k.wav"
    if not extract_audio(cfg, clip, wav):
        return [], "none"
    phrases, mean_db = speech_phrases(wav, au)
    if not phrases or mean_db < au["silence_db"] - 10:
        return [], "silent"
    groups, cur = [], None                                   # merge phrases into <= 25 s requests
    for a, b in phrases:
        if cur and b - cur[0] <= au["max_stt_chunk_s"] and a - cur[1] < 1.5:
            cur[1] = b
        else:
            if cur:
                groups.append(cur)
            cur = [a, b]
    groups.append(cur)
    lines = []
    for a, b in groups[: au["max_stt_requests_per_clip"]]:
        text = transcribe(cfg, wav, a, b, workdir / "stt_part.wav")
        if text:
            lines.append({"in": a, "out": b, "text": text})
    words = sum(len(l["text"].split()) for l in lines)
    return (lines, "speech") if words >= au["min_words"] else ([], "music_or_ambient")


# ------------------------------------------------------------------ stage C: Claude vision

VISION_SYSTEM = """You are a senior video editor for premium real-estate ads (villas, farmland plots, gated communities in India).
You review raw footage frame by frame and decide which parts are good enough for a high-retention 9:16 ad.
You are strict: a segment is only worth keeping if it looks premium, is clearly composed and shows something a buyer cares about.
Reply with JSON only."""


def vision_review(cfg, item, meta, vision_frames, candidates, speech=None):
    max_frames = cfg["analysis"]["max_vision_frames"]
    idx = list(range(len(vision_frames)))
    if len(idx) > max_frames:
        idx = [round(i * (len(vision_frames) - 1) / (max_frames - 1)) for i in range(max_frames)]
    content = [{"type": "text", "text": (
        f"Clip: {item['name']} | project: {item['project']} | {meta['width']}x{meta['height']} | "
        f"{meta['duration_s']} s.\nFrames follow, one per second, each labelled with its timestamp.")}]
    for i in idx:
        content.append({"type": "text", "text": f"t={i / VISION_FPS:.0f}s"})
        content.append(image_block(vision_frames[i].read_bytes()))
    seg_lines = "\n".join(f"- {s['segment_id']}: {s['in']}s to {s['out']}s" for s in candidates) or "(none)"
    blocking = ", ".join(cfg["analysis"]["blocking_problems"])
    speech_txt = "\n".join(f"- {l['in']}s to {l['out']}s: \"{l['text']}\"" for l in (speech or [])) or "(no speech)"
    content.append({"type": "text", "text": f"""Technically clean candidate segments (already free of blur, shake and bad exposure):
{seg_lines}

What is SPOKEN in this clip (speech-to-text, with times):
{speech_txt}

Some clips are already-edited videos, testimonials or presenter pieces with their own meaningful audio.
In "native_segments", list stretches whose OWN audio should be kept in an ad instead of being covered by a new voiceover:
a buyer testimonial, a founder or presenter explaining the project, a clear spoken claim with matching visuals.
Each must start and end on the speech times above (use whole lines), last 2-15 s, sound clean, and be strong enough for a premium ad.
Skip filler, poor audio, mumbling, or speech unrelated to the property. Empty list if nothing qualifies.

For EVERY candidate segment return an entry. Return JSON:
{{
  "clip_summary": "<one line: what the whole clip shows>",
  "is_edited_video": <true if this is already an edited video or ad (cuts, graphics, music) rather than raw footage>,
  "has_burned_captions": <true if text captions are already burned into the picture>,
  "native_segments": [
    {{"in": <s>, "out": <s>, "transcript": "<exact words>", "kind": "<testimonial | presenter | claim | other>",
      "ad_score": <0-10>, "description": "<what is seen while it is said>", "subject_x": <0-1>, "why": "<why it is worth keeping>"}}
  ],
  "segments": [
    {{
      "segment_id": "<id from the list>",
      "keep": true,
      "ad_score": <0-10, how premium and useful for an ad>,
      "description": "<one line, concrete: what is visible and what happens, e.g. 'drone rises over villa rooftops; pool visible from 8 s'>",
      "shot_type": "<aerial | exterior | interior | amenity | landscape | road_access | lifestyle | plot | construction | other>",
      "camera_move": "<static | push_in | pull_out | pan | tilt | orbit | rise | descend | tracking | handheld>",
      "tags": ["<3-6 short tags: subjects, time of day, mood>"],
      "best_in": <seconds, start of the strongest part, inside the segment>,
      "best_out": <seconds, end of the strongest part, inside the segment>,
      "hero_second": <the single best moment, seconds>,
      "subject_x": <0-1 horizontal centre of the main subject, used for the 9:16 crop>,
      "problems": ["<any of: {blocking}, horizon_tilt, low_resolution, people_background>. text_on_screen = ANY burned-in caption, title or logo text; letterboxed_or_framed = black bars, borders, rounded frame or picture-in-picture"],
      "reason": "<if keep is false or score < 6, why>"
    }}
  ]
}}"""})
    return ask_claude_json(cfg, "vision_model", VISION_SYSTEM, content, max_tokens=4000)


# ------------------------------------------------------------------ stage D + driver

def native_segments(cfg, item, meta, speech, picks):
    """Stretches whose own audio is kept. Snapped to speech-line boundaries so words are never cut."""
    au, out = cfg["audio"], []
    starts = [l["in"] for l in speech]
    ends = [l["out"] for l in speech]
    for n, p in enumerate(picks, 1):
        try:
            a, b = float(p["in"]), float(p["out"])
        except (KeyError, TypeError, ValueError):
            continue
        if starts:
            a = min(starts, key=lambda x: abs(x - a))
            b = min(ends, key=lambda x: abs(x - b))
        a, b = max(0.0, a - 0.1), min(meta["duration_s"], b + 0.25)
        seg = {
            "segment_id": f"{item['id']}_n{n:02d}", "native_audio": True,
            "in": round(a, 2), "out": round(b, 2), "usable_s": round(b - a, 2),
            "transcript": p.get("transcript", ""), "kind": p.get("kind", "other"),
            "ad_score": int(p.get("ad_score", 0) or 0), "description": p.get("description", ""),
            "shot_type": "native_" + str(p.get("kind", "other")), "camera_move": "static", "tags": [],
            "hero_second": round(a, 2), "problems": [],
            "subject_x": min(max(float(p["subject_x"] if p.get("subject_x") is not None else 0.5), 0.0), 1.0),
        }
        if not (au["min_native_s"] <= seg["usable_s"] <= au["max_native_s"]):
            seg.update(status="rejected", reject_reason=f"native audio {seg['usable_s']} s outside {au['min_native_s']}-{au['max_native_s']} s")
        elif seg["ad_score"] < cfg["analysis"]["min_ad_score"]:
            seg.update(status="rejected", reject_reason=f"native audio score {seg['ad_score']}")
        else:
            seg["status"] = "approved"
        out.append(seg)
    return out


def analyze_clip(cfg, item, use_vision=True):
    paths, th, an = cfg["_paths"], cfg["thresholds_clip"], cfg["analysis"]
    clip = fetch_clip(cfg, item)
    meta = probe(clip)
    if meta["duration_s"] <= 0:
        raise RuntimeError("unreadable video")
    if meta["duration_s"] < an.get("min_clip_s", 3.0):          # Live Photos and fragments
        if not item.get("_local"):
            Path(clip).unlink(missing_ok=True)
        return {"file_id": item["id"], "name": item["name"], "project": item["project"],
                "drive_path": item.get("drive_path", item["name"]), "modifiedTime": item.get("modifiedTime"),
                **meta, "analysis_version": ANALYSIS_VERSION, "segments": [],
                "skipped": f"too short ({meta['duration_s']} s)"}
    proxy = paths["proxies"] / f"{item['id']}.mp4" if an.get("make_proxies") else None
    frames_dir = paths["frames"] / item["id"]
    a_frames, v_frames = extract_frames(cfg, clip, frames_dir, proxy)

    rows = technical_scan(a_frames, th)
    candidates, rejects = candidate_segments(rows, meta["duration_s"], th)
    for n, s in enumerate(candidates, 1):
        s["segment_id"] = f"{item['id']}_s{n:02d}"

    has_audio = has_audio_stream(cfg, clip)
    speech, audio_kind = [], "none"
    if has_audio and cfg["audio"].get("enabled", True):
        try:
            speech, audio_kind = audio_scan(cfg, clip, frames_dir)
        except Exception as e:
            log("analyze", f"{item['name']}: speech-to-text skipped ({e})")
            audio_kind = "unknown"

    entry = {
        "file_id": item["id"], "name": item["name"], "project": item["project"],
        "drive_path": item.get("drive_path", item["name"]), "modifiedTime": item.get("modifiedTime"),
        **meta, "has_audio": has_audio, "audio_kind": audio_kind, "speech": speech,
        "is_edited_video": False, "has_burned_captions": False,
        "low_resolution": min(meta["width"], meta["height"]) < an["min_short_side_px"],
        "proxy": str(proxy) if proxy and proxy.exists() else None,
        "local_path": str(clip), "analysis_version": ANALYSIS_VERSION,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "clip_summary": "", "segments": [],
    }

    review = {}
    if (candidates or speech) and use_vision:
        result = vision_review(cfg, item, meta, v_frames, candidates, speech)
        entry["clip_summary"] = result.get("clip_summary", "")
        entry["is_edited_video"] = bool(result.get("is_edited_video"))
        entry["has_burned_captions"] = bool(result.get("has_burned_captions"))
        review = {s.get("segment_id"): s for s in result.get("segments", [])}
        entry["segments"] += native_segments(cfg, item, meta, speech, result.get("native_segments") or [])

    blocking = set(an["blocking_problems"])
    for s in candidates:
        v = review.get(s["segment_id"], {})
        seg = dict(s)
        if use_vision and not v:
            seg.update(status="rejected", reject_reason="no vision verdict")
            entry["segments"].append(seg)
            continue
        b_in = float(v.get("best_in", s["in"]) or s["in"])
        b_out = float(v.get("best_out", s["out"]) or s["out"])
        b_in, b_out = max(s["in"], b_in), min(s["out"], b_out)
        if b_out - b_in < th["min_segment_s"]:
            b_in, b_out = s["in"], s["out"]
        hero = float(v.get("hero_second", (b_in + b_out) / 2) or (b_in + b_out) / 2)
        seg.update({
            "in": round(b_in, 2), "out": round(b_out, 2), "usable_s": round(b_out - b_in, 2),
            "ad_score": int(v.get("ad_score", 6 if not use_vision else 0)),
            "description": v.get("description", ""), "shot_type": v.get("shot_type", "other"),
            "camera_move": v.get("camera_move", "static"), "tags": v.get("tags", []),
            "hero_second": round(min(max(hero, b_in), b_out), 2),
            "subject_x": min(max(float(v["subject_x"] if v.get("subject_x") is not None else 0.5), 0.0), 1.0),
            "problems": v.get("problems", []),
        })
        hit = blocking.intersection(seg["problems"])
        if use_vision and not v.get("keep", False):
            seg.update(status="rejected", reject_reason=v.get("reason") or "editor rejected")
        elif seg["ad_score"] < an["min_ad_score"]:
            seg.update(status="rejected", reject_reason=f"ad score {seg['ad_score']} < {an['min_ad_score']}: {v.get('reason', '')}".strip(": "))
        elif hit:
            seg.update(status="rejected", reject_reason="problems: " + ", ".join(sorted(hit)))
        else:
            seg["status"] = "approved"
        entry["segments"].append(seg)

    entry["segments"].extend(rejects)
    entry["segments"].sort(key=lambda s: s["in"])
    if not an.get("keep_frames", True):
        shutil.rmtree(frames_dir, ignore_errors=True)
    # The proxy carries picture + audio, so the big Drive original is no longer needed on disk.
    if not item.get("_local") and not an.get("keep_originals", False) and entry["proxy"]:
        Path(clip).unlink(missing_ok=True)
        entry["local_path"] = None
    return entry


def write_summary(cfg, catalog):
    lines = [f"# Clip catalog summary\n\nGenerated {datetime.now():%Y-%m-%d %H:%M}.\n"]
    by_project = {}
    for c in catalog["clips"].values():
        by_project.setdefault(c["project"], []).append(c)
    for project, clips in sorted(by_project.items()):
        approved = [(c, s) for c in clips for s in c["segments"] if s.get("status") == "approved" and not s.get("native_audio")]
        total = sum(s["usable_s"] for _, s in approved)
        lines.append(f"\n## {project}\n\n{len(clips)} clips, {len(approved)} approved segments, {total:.0f} s usable.\n")
        by_type = {}
        for c, s in approved:
            by_type.setdefault(s["shot_type"], []).append((c, s))
        for st, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"\n### {st} ({len(items)})\n")
            for c, s in sorted(items, key=lambda cs: -cs[1]["ad_score"]):
                lines.append(f"- **{s['ad_score']}/10** `{c['name']}` {s['in']}-{s['out']} s: {s['description']}")
        native = [(c, s) for c in clips for s in c["segments"] if s.get("native_audio") and s.get("status") == "approved"]
        if native:
            lines.append(f"\n### Own audio kept ({len(native)})\n")
            for c, s in native:
                lines.append(f"- **{s['ad_score']}/10** `{c['name']}` {s['in']}-{s['out']} s ({s['kind']}): \"{s['transcript']}\"")
        unusable = [c for c in clips if not any(s.get("status") == "approved" for s in c["segments"])]
        if unusable:
            lines.append("\n### Clips with nothing usable\n")
            for c in unusable:
                reasons = sorted({s.get("reject_reason", "") for s in c["segments"]} - {""})
                lines.append(f"- `{c['drive_path']}`: {'; '.join(reasons)[:200] or c.get('error', 'no clean segment')}")
    path = cfg["_paths"]["catalog"] / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--drive", action="store_true", help="analyse drive.raw_folder_id")
    src.add_argument("--local", help="analyse a local folder")
    ap.add_argument("--force", action="store_true", help="re-analyse clips already in the catalog")
    ap.add_argument("--limit", type=int, default=0, help="only the first N new clips")
    ap.add_argument("--only", nargs="+", help="only clips whose folder path contains one of these words")
    ap.add_argument("--skip", nargs="+", help="skip clips whose folder path contains one of these words")
    ap.add_argument("--max-mb", type=float, default=0, help="skip files bigger than this (MB)")
    ap.add_argument("--min-mb", type=float, default=1, help="skip files smaller than this (MB)")
    ap.add_argument("--no-vision", action="store_true", help="technical stage only (no API cost)")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cat_path = cfg["_paths"]["catalog_file"]
    catalog = read_json(cat_path, {"clips": {}})
    items = collect_sources(cfg, args)
    where = lambda i: f"{i['project']}/{i.get('drive_path', '')}".lower()
    if args.only:
        items = [i for i in items if any(w.lower() in where(i) for w in args.only)]
    if args.skip:
        items = [i for i in items if not any(w.lower() in where(i) for w in args.skip)]
    if args.max_mb:
        items = [i for i in items if int(i.get("size", 0) or 0) <= args.max_mb * 1e6]
    items = [i for i in items if int(i.get("size", 0) or 0) >= args.min_mb * 1e6 or i.get("_local")]   # tiny = broken / Live Photo
    items.sort(key=lambda i: int(i.get("size", 0) or 0))       # small clips first: usable footage builds fast
    todo = []
    for it in items:
        old = catalog["clips"].get(it["id"])
        fresh = old and old.get("modifiedTime") == it.get("modifiedTime") and \
            old.get("analysis_version") == ANALYSIS_VERSION and "error" not in old
        if args.force or not fresh:
            todo.append(it)
    if args.limit:
        todo = todo[:args.limit]
    log("analyze", f"{len(items)} clips found, {len(todo)} to analyse")

    workers = args.workers or cfg["analysis"]["workers"]
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(analyze_clip, cfg, it, not args.no_vision): it for it in todo}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                entry = fut.result()
                ok = sum(1 for s in entry["segments"] if s.get("status") == "approved")
                log("analyze", f"{it['name']}: {ok} approved / {len(entry['segments'])} segments")
            except Exception as e:  # keep going; record the failure
                entry = {"file_id": it["id"], "name": it["name"], "project": it["project"],
                         "drive_path": it.get("drive_path", it["name"]), "segments": [], "error": str(e)}
                log("analyze", f"FAILED {it['name']}: {e}")
            with _lock:
                catalog["clips"][it["id"]] = entry
                write_json(cat_path, catalog)
            done += 1
    summary = write_summary(cfg, catalog)
    log("analyze", f"done: {done} analysed. Catalog: {cat_path}  Summary: {summary}")


if __name__ == "__main__":
    main()
