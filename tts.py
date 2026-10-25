"""Voiceover: one Sarvam TTS request per sentence (in parallel), silence trimmed, then joined.

Writes runs/<id>/audio/s01.wav ... and voiceover.wav; returns measured durations.
  python tts.py --run-dir workspace/runs/<run_id> [--mock]
"""
import argparse
import base64
import json
import os
import subprocess
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from common import ffmpeg_bin, load_config, log, read_json, write_json

SAMPLE_RATE = 44100


def wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def sarvam_request(cfg, text):
    t = cfg["tts"]
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not set (put it in .env), or run with --mock.")
    body = {"target_language_code": t["language_code"], "speaker": t["speaker"],
            "model": t["model"], "pace": t.get("pace", 1.0)}
    if t.get("sample_rate"):
        body["speech_sample_rate"] = t["sample_rate"]
    if t.get("request_style", "text") == "inputs":       # older bulbul:v1 style
        body["inputs"] = [text]
    else:
        body["text"] = text
    for attempt in range(4):
        r = requests.post(t["url"], json=body, timeout=60,
                          headers={"api-subscription-key": key, "content-type": "application/json"})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Sarvam {r.status_code}: {r.text[:300]}")
        return base64.b64decode(r.json()["audios"][0])
    raise RuntimeError("Sarvam: too many retries")


def edge_request(cfg, text, dst_mp3):
    """TEMPORARY test voice (Microsoft neural TTS via edge-tts) for when Sarvam has no credit.
    Enable with tts.provider: edge. Production voice is Sarvam."""
    import asyncio
    import edge_tts
    e = cfg["tts"].get("edge", {})
    last = None
    for attempt in range(10):                       # the free endpoint drops connections intermittently
        try:
            comm = edge_tts.Communicate(text, e.get("voice", "en-IN-NeerjaNeural"), rate=e.get("rate", "+8%"))
            asyncio.run(comm.save(str(dst_mp3)))
            return
        except Exception as err:
            last = err
            time.sleep(min(1.5 * (attempt + 1), 8))
    raise RuntimeError(f"edge-tts failed after retries: {last}")


def trim_and_normalise(cfg, src, dst):
    """Trim leading/trailing silence only (keeps natural pauses inside the sentence)."""
    th = cfg["tts"].get("silence_db", -45)
    af = (f"silenceremove=start_periods=1:start_threshold={th}dB:start_silence=0.05,"
          f"areverse,silenceremove=start_periods=1:start_threshold={th}dB:start_silence=0.08,areverse")
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    "-af", af, "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)


def mock_audio(cfg, text, dst):
    secs = max(0.8, len(text.split()) / cfg["director"]["words_per_second"])
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency=220:sample_rate={SAMPLE_RATE}:duration={secs:.2f}",
                    "-af", "volume=0.05", "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)


def original_clip(cfg, clip):
    """The original file (proxies have no audio)."""
    for p in (clip.get("local_path"), clip.get("proxy")):       # proxies keep the clip's audio track
        if p and Path(p).exists():
            return Path(p)
    hits = [h for h in cfg["_paths"]["clips"].glob(f"{clip['file_id']}.*") if not h.name.endswith(".part")]
    if hits:
        return hits[0]
    import drive
    dest = cfg["_paths"]["clips"] / f"{clip['file_id']}{Path(clip['name']).suffix or '.mp4'}"
    return drive.download(clip["file_id"], dest)


def native_audio(cfg, clip, seg, dst):
    """Cut the clip's own audio for a native segment, loudness-matched to the voiceover."""
    src = original_clip(cfg, clip)
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{seg['in']:.3f}", "-t", f"{seg['out'] - seg['in']:.3f}", "-i", str(src),
                    "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.05",
                    "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)


def synthesize(cfg, script, run_dir, mock=False, catalog=None):
    run_dir = Path(run_dir)
    adir = run_dir / "audio"
    adir.mkdir(parents=True, exist_ok=True)
    native_by_id = {}
    for c in (catalog or {}).get("clips", {}).values():
        for sg in c.get("segments", []):
            if sg.get("native_audio"):
                native_by_id[sg["segment_id"]] = (c, sg)

    def one(s):
        out = adir / f"{s['id']}.wav"
        if s.get("caption_style") == "native":
            clip, seg = native_by_id[s["segment_ids"][0]]
            native_audio(cfg, clip, seg, out)
        elif mock:
            mock_audio(cfg, s["text"], out)
        elif cfg["tts"].get("provider") in ("chatterbox", "indic_parler", "kokoro"):
            from local_models import synthesize_local
            raw = adir / f"{s['id']}_raw.wav"
            synthesize_local(cfg, s["text"], raw)
            trim_and_normalise(cfg, raw, out)
            raw.unlink(missing_ok=True)
        elif cfg["tts"].get("provider") == "edge":
            raw = adir / f"{s['id']}_raw.mp3"
            edge_request(cfg, s["text"], raw)
            trim_and_normalise(cfg, raw, out)
            raw.unlink(missing_ok=True)
        else:
            raw = adir / f"{s['id']}_raw.wav"
            raw.write_bytes(sarvam_request(cfg, s["text"]))
            trim_and_normalise(cfg, raw, out)
            raw.unlink(missing_ok=True)
        return {"id": s["id"], "path": str(out), "duration": round(wav_duration(out), 3),
                "native": s.get("caption_style") == "native"}

    workers = 1 if cfg["tts"].get("provider") != "sarvam" else cfg["tts"].get("parallel_requests", 4)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(one, script["sentences"]))

    # join with a short breath between sentences
    gap = cfg["tts"].get("gap_seconds", 0.15)
    gap_wav = adir / "_gap.wav"
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-t", str(gap), "-c:a", "pcm_s16le", str(gap_wav)],
                   check=True)
    lst = adir / "_concat.txt"
    lines = []
    for i, p in enumerate(parts):
        lines.append(f"file '{Path(p['path']).name}'")
        if i < len(parts) - 1:
            lines.append(f"file '{gap_wav.name}'")
    lst.write_text("\n".join(lines), encoding="utf-8")
    vo = run_dir / "voiceover.wav"
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst.name, "-c:a", "pcm_s16le", str(vo.resolve())], check=True, cwd=adir)
    meta = {"sentences": parts, "gap_seconds": gap, "voiceover": str(vo),
            "total_seconds": round(wav_duration(vo), 3), "mock": mock}
    write_json(run_dir / "audio_meta.json", meta)
    log("tts", f"{len(parts)} sentences, {meta['total_seconds']} s{' (mock)' if mock else ''}")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--mock", action="store_true", help="no API: quiet tone of estimated length")
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    m = synthesize(cfg, read_json(Path(a.run_dir) / "script.json"), a.run_dir, mock=a.mock,
                   catalog=read_json(cfg["_paths"]["catalog_file"], {"clips": {}}))
    print(json.dumps({"total_seconds": m["total_seconds"]}))
