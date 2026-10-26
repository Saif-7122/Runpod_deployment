"""Render timeline.json to a 1080x1920 MP4 with one ffmpeg command (NVENC on the pod, x264 locally).

  python render.py --run-dir workspace/runs/<run_id>
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

from analyze import encoder_args
from common import ROOT, ffmpeg_bin, load_config, log, read_json, write_json


def resolve_source(cfg, scene):
    """Full-quality original first (renders from proxies look soft); proxy only if the original is unavailable."""
    hits = [h for h in cfg["_paths"]["clips"].glob(f"{scene['clip_file_id']}.*") if not h.name.endswith(".part")]
    if hits:
        return hits[0], False
    proxy = cfg["_paths"]["proxies"] / f"{scene['clip_file_id']}.mp4"
    if proxy.exists() and not cfg["rendering"].get("prefer_originals", True):
        return proxy, True
    try:
        import drive
        dest = cfg["_paths"]["clips"] / f"{scene['clip_file_id']}{Path(scene['clip_name']).suffix or '.mp4'}"
        log("render", f"downloading original {scene['clip_name']}")
        return drive.download(scene["clip_file_id"], dest), False
    except Exception as e:
        if proxy.exists():
            log("render", f"original unavailable ({e}); using proxy for {scene['clip_name']}")
            return proxy, True
        raise


def draft_encoder_args(rc):
    if rc["video_codec"] == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", "30", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"]


def final_encoder_args(rc):
    if rc["video_codec"] == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", rc.get("nvenc_preset", "p6"), "-tune", "hq", "-rc", "vbr",
                "-cq", str(rc.get("cq", 19)), "-b:v", "0", "-maxrate", rc.get("maxrate", "16M"),
                "-bufsize", "32M", "-profile:v", "high"]
    return ["-c:v", "libx264", "-preset", rc.get("x264_preset", "medium"), "-crf", str(rc.get("crf", 18)),
            "-maxrate", rc.get("maxrate", "16M"), "-bufsize", "32M", "-profile:v", "high"]


def filter_path(p):
    """Path inside an ffmpeg filter argument (escape drive-letter colon on Windows)."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def build_command(cfg, timeline, run_dir, out_path, draft=False):
    rc, cap = cfg["rendering"], cfg["captions"]
    W, H, fps = (540, 960, 24) if draft else (1080, 1920, rc.get("fps", 30))
    total = timeline["total_duration_seconds"]
    cmd = [ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y"]
    chains = []
    for i, sc in enumerate(timeline["timeline"]):
        src, _ = resolve_source(cfg, sc)
        take = max(0.1, sc["duration"] - sc["hold_seconds"]) + 0.15
        if rc.get("hw_decode"):
            cmd += ["-hwaccel", "cuda"]
        cmd += ["-ss", f"{sc['source_in']:.3f}", "-t", f"{take:.3f}", "-i", str(src)]
        fx = min(max(float(sc.get("crop_focus_x", 0.5)), 0.0), 1.0)
        # shot shorter than its line: gentle slow motion (max 1.5x) instead of a frozen last frame
        stretch = min(1.5, sc["duration"] / max(0.1, sc["duration"] - sc["hold_seconds"])) if sc["hold_seconds"] > 0.05 else 1.0
        slow = f"setpts={stretch:.3f}*PTS," if stretch > 1.0 else ""
        chains.append(
            f"[{i}:v]{slow}scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H}:(iw-{W})*{fx:.3f}:(ih-{H})/2,setsar=1,fps={fps},"
            f"{'unsharp=5:5:0.45:5:5:0,' if rc.get('sharpen', True) else ''}format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration={sc['hold_seconds'] + 0.5:.3f},"
            f"trim=duration={sc['duration']:.3f},setpts=PTS-STARTPTS[v{i}]")
    n = len(timeline["timeline"])
    concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]"
    subs = f"subtitles=captions.ass"
    if cap.get("fonts_dir"):
        fd = Path(cap["fonts_dir"])
        fd = fd if fd.is_absolute() else ROOT / fd
        subs += f":fontsdir='{filter_path(fd)}'"
    chains += [concat, f"[vc]{subs}[vout]"]

    vo_idx = n
    cmd += ["-i", str(Path(run_dir) / timeline["voiceover_audio"])]
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"
    music = rc.get("music_path")
    if music and Path(music).exists():
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        chains += [
            f"[{vo_idx}:a]aresample=48000,apad,atrim=0:{total:.3f},asplit[vo1][vo2]",
            f"[{vo_idx + 1}:a]aresample=48000,volume={rc.get('music_volume', 0.15)},atrim=0:{total:.3f}[m]",
            "[m][vo1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md]",
            f"[vo2][md]amix=inputs=2:duration=first:normalize=0,{loud}[aout]",
        ]
    else:
        chains.append(f"[{vo_idx}:a]aresample=48000,apad,atrim=0:{total:.3f},{loud}[aout]")

    cmd += ["-filter_complex", ";".join(chains), "-map", "[vout]", "-map", "[aout]",
            *(draft_encoder_args(rc) if draft else final_encoder_args(rc)), "-r", str(fps), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-t", f"{total:.3f}", "-movflags", "+faststart"]
    if rc.get("threads"):
        cmd += ["-threads", str(rc["threads"])]
    cmd.append(str(out_path))
    return cmd


def render(cfg, run_dir, draft=False):
    """draft=True: quick 540x960 preview for the video judge (seconds on the GPU)."""
    run_dir = Path(run_dir).resolve()
    tl = read_json(run_dir / "timeline.json")
    out = run_dir / ("draft.mp4" if draft else "finished_ad.mp4")
    cmd = build_command(cfg, tl, run_dir, out, draft)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True, errors="ignore")
    if r.returncode != 0:
        (run_dir / "ffmpeg_cmd.txt").write_text(" ".join(f'"{c}"' if " " in c else c for c in cmd), encoding="utf-8")
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-1500:]}")
    secs = time.time() - t0
    if draft:
        log("render", f"draft {out.name} in {secs:.1f} s")
        return out, secs
    write_json(run_dir / "edit_project_source.json", {
        "video_title": tl["video_title"], "angle": tl.get("angle"), "resolution": "1080x1920",
        "total_duration_seconds": tl["total_duration_seconds"],
        "voiceover": tl["voiceover"], "timeline": tl["timeline"], "missing_shots": tl.get("missing_shots", []),
        "files": {"video": "finished_ad.mp4", "voiceover": "voiceover.wav", "captions": "captions.ass"},
        "how_to_rebuild": "Each scene = clip_name trimmed from source_in for duration seconds (from the original "
                          "clip, or the 1080-wide proxy if source_is_proxy), cropped 9:16 around crop_focus_x. "
                          "Voiceover and captions are included as separate files.",
    })
    log("render", f"{out.name} in {secs:.1f} s")
    return out, secs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    path, secs = render(cfg, a.run_dir)
    print(json.dumps({"video": str(path), "render_seconds": round(secs, 1)}))
