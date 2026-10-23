"""Fit the script to the measured voiceover: scene times, in-points inside approved segments, captions.

Writes timeline.json and captions.ass.
  python fit_timeline.py --run-dir workspace/runs/<run_id>
"""
import argparse
import json
import re
from pathlib import Path

from common import load_config, log, read_json, write_json
from judge import segment_index


def fit(cfg, script, audio_meta, catalog, run_dir):
    segs = segment_index(catalog)
    clips = catalog["clips"]
    gap = audio_meta.get("gap_seconds", 0.0)
    tail = cfg["rendering"].get("tail_seconds", 0.5)
    durs = {p["id"]: p["duration"] for p in audio_meta["sentences"]}

    scenes, voice, t = [], [], 0.0
    sents = script["sentences"]
    for k, s in enumerate(sents):
        d = durs[s["id"]]
        voice.append({"id": s["id"], "text": s["text"], "start": round(t, 3), "end": round(t + d, 3)})
        window = d + (gap if k < len(sents) - 1 else tail)
        ids = s["segment_ids"]
        piece = window / len(ids)
        for j, sid in enumerate(ids):
            seg = segs[sid]
            start = t + j * piece
            usable = seg["out"] - seg["in"]
            if seg.get("native_audio"):                            # picture locked to its own audio
                src_in, hold = seg["in"], max(0.0, piece - usable)
            elif usable >= piece:
                ideal = seg["hero_second"] - piece * 0.35          # hero lands early in the cut
                src_in = min(max(ideal, seg["in"]), seg["out"] - piece)
                hold = 0.0
            else:
                src_in, hold = seg["in"], piece - usable           # render holds the last frame
            clip = clips[seg["file_id"]]
            scenes.append({
                "scene": len(scenes) + 1, "sentence": s["id"],
                "start_time": round(start, 3), "end_time": round(start + piece, 3), "duration": round(piece, 3),
                "segment_id": sid, "clip_file_id": seg["file_id"], "clip_name": clip["name"],
                "source_path": clip.get("proxy") or clip.get("local_path"),
                "source_is_proxy": bool(clip.get("proxy")),
                "source_in": round(src_in, 3), "hold_seconds": round(hold, 3),
                "crop_focus_x": seg.get("subject_x", 0.5),
                "text_overlay": s.get("overlay", "") if j == 0 else "",
                "caption_style": s.get("caption_style", "normal"),
                "native_audio": bool(seg.get("native_audio")),
                "burned_captions": bool(clip.get("has_burned_captions")),
                "description": seg.get("description", ""),
            })
        t += window

    timeline = {
        "run_id": Path(run_dir).name, "video_title": script.get("video_title", ""),
        "angle": script.get("angle", ""), "project": script.get("project"),
        "total_duration_seconds": round(t, 3), "voiceover_audio": "voiceover.wav",
        "voiceover": voice, "timeline": scenes, "missing_shots": script.get("missing_shots", []),
    }
    write_json(Path(run_dir) / "timeline.json", timeline)
    write_captions(cfg, timeline, sents, Path(run_dir) / "captions.ass")
    log("fit", f"{len(scenes)} cuts over {t:.1f} s")
    return timeline


# ------------------------------------------------------------------ captions (ASS)

def ts(x):
    cs = int(round(x * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def esc(text):
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def chunks(text, n):
    w = text.split()
    return [" ".join(w[i:i + n]) for i in range(0, len(w), n)]


def write_captions(cfg, timeline, sents, path):
    c = cfg["captions"]
    font, size = c["font"], c["size"]
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,80,80,{c['caption_margin_v']},1
Style: Hook,{font},{int(size * 1.15)},&H0000E5FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,80,80,{c['caption_margin_v']},1
Style: Overlay,{font},{c['overlay_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,18,0,8,80,80,{c['overlay_margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    by_id = {s["id"]: s for s in sents}
    for v in timeline["voiceover"]:
        s = by_id[v["id"]]
        if any(sc["sentence"] == v["id"] and sc.get("burned_captions") and sc.get("native_audio")
               for sc in timeline["timeline"]):
            continue                                                 # clip already has its own captions
        style = "Hook" if s.get("caption_style") == "hook" else "Caption"
        parts = chunks(v["text"], c["words_per_caption"])
        weights = [max(1, len(re.sub(r"\W", "", p))) for p in parts]
        span, t = v["end"] - v["start"], v["start"]
        for p, wgt in zip(parts, weights):
            d = span * wgt / sum(weights)
            ev.append(f"Dialogue: 1,{ts(t)},{ts(t + d)},{style},,0,0,0,,{{\\fad(60,0)}}{esc(p.upper() if c.get('uppercase') else p)}")
            t += d
    for sc in timeline["timeline"]:
        if sc["text_overlay"]:
            end = max(x["end_time"] for x in timeline["timeline"] if x["sentence"] == sc["sentence"])
            ev.append(f"Dialogue: 0,{ts(sc['start_time'])},{ts(end)},Overlay,,0,0,0,,{{\\fad(120,80)}}{esc(sc['text_overlay'].upper())}")
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    run = Path(a.run_dir)
    tl = fit(cfg, read_json(run / "script.json"), read_json(run / "audio_meta.json"),
             read_json(cfg["_paths"]["catalog_file"]), run)
    print(json.dumps({"scenes": len(tl["timeline"]), "seconds": tl["total_duration_seconds"]}))
