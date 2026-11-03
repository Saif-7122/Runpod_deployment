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
from speakable import speakable

SAMPLE_RATE = 44100


def wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def voice_for(cfg, language):
    """Per-language Sarvam settings: tts.languages.<en|te> overrides the defaults."""
    t = dict(cfg["tts"])
    t.update((t.get("languages") or {}).get(language or "en", {}))
    return t


def sarvam_request(cfg, text, language="en"):
    t = voice_for(cfg, language)
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


def plain(text):
    """Script text without *stress* markers (those only style the captions)."""
    return text.replace("*", "")


def elevenlabs_script(cfg, script, adir):
    """The whole script in ONE ElevenLabs request (natural flow between lines), split back into one wav per
    sentence at the middle of each pause, using the character timestamps ElevenLabs returns."""
    e = cfg["tts"]["elevenlabs"]
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set (put it in .env).")
    lang = script.get("language", "en")
    name = script.get("voice") or e["defaults"].get(lang, e["defaults"]["en"])
    voice_id = e["voices"].get(name, name)
    sents = script["sentences"]
    texts = [speakable(plain(s["text"])) for s in sents]          # numbers in English words in every language (user)
    body = {"text": " ".join(texts), "model_id": e["model"], "voice_settings": e.get("voice_settings", {}),
            "language_code": lang}
    for attempt in range(4):
        r = requests.post(e["url"].format(voice_id=voice_id), params={"output_format": e["output_format"]},
                          headers={"xi-api-key": key, "content-type": "application/json"}, json=body, timeout=180)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt + 1)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
        break
    else:
        raise RuntimeError("ElevenLabs: too many retries")
    data = r.json()
    al = data.get("normalized_alignment") or data["alignment"]
    starts, ends = al["character_start_times_seconds"], al["character_end_times_seconds"]
    full = adir / "_full.wav"
    mp3 = adir / "_full.mp3"
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3),
                    "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(full)], check=True)
    total = wav_duration(full)
    # each sentence's first/last spoken character time (alignment chars follow the joined text)
    spans, pos = [], 0
    n = len(starts)
    for t in texts:
        a, b = min(pos, n - 1), min(pos + len(t) - 1, n - 1)
        spans.append((starts[a], ends[b]))
        pos += len(t) + 1
    cuts = [max(0.0, spans[0][0] - 0.05)] + [(spans[i][1] + spans[i + 1][0]) / 2 for i in range(len(spans) - 1)] + \
           [min(total, spans[-1][1] + 0.25)]
    parts = []
    for i, s in enumerate(sents):
        out = adir / f"{s['id']}.wav"
        subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(full),
                        "-af", f"atrim={cuts[i]:.3f}:{cuts[i + 1]:.3f},asetpts=PTS-STARTPTS",
                        "-c:a", "pcm_s16le", str(out)], check=True)
        parts.append({"id": s["id"], "path": str(out), "duration": round(wav_duration(out), 3), "native": False})
    mp3.unlink(missing_ok=True)
    full.unlink(missing_ok=True)
    log("tts", f"ElevenLabs {name} ({e['model']}): {len(body['text'])} characters")
    return parts


def trim_and_normalise(cfg, src, dst, language="en"):
    """Trim leading/trailing silence only (keeps natural pauses), plus the configured pitch shift."""
    t = voice_for(cfg, language)
    th = t.get("silence_db", -45)
    af = (f"silenceremove=start_periods=1:start_threshold={th}dB:start_silence=0.05,"
          f"areverse,silenceremove=start_periods=1:start_threshold={th}dB:start_silence=0.08,areverse")
    semis = float(t.get("pitch_semitones", 0) or 0)
    if abs(semis) > 0.01:                       # pitch up/down without changing speed
        r = 2 ** (semis / 12)
        af += f",asetrate={SAMPLE_RATE}*{r:.5f},aresample={SAMPLE_RATE},atempo={1 / r:.5f}"
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    "-af", f"aresample={SAMPLE_RATE}," + af, "-ar", str(SAMPLE_RATE), "-ac", "1",
                    "-c:a", "pcm_s16le", str(dst)], check=True)


def mock_audio(cfg, text, dst, language="en"):
    from director import wps_for                 # Telugu is spoken slower than English: time the blank track to match
    secs = max(0.8, len(text.split()) / wps_for(cfg, language))
    subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"anullsrc=channel_layout=mono:sample_rate={SAMPLE_RATE}", "-t", f"{secs:.2f}",
                    "-c:a", "pcm_s16le", str(dst)], check=True)                  # blank track until Sarvam is loaded


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

    scenic = script.get("mode") == "scenic"           # text-on-screen reel: no voice, silence for the music

    def one(s):
        out = adir / f"{s['id']}.wav"
        lang = script.get("language", "en")
        s = {**s, "text": speakable(plain(s["text"]))}   # digits -> English words in every language, no markers
        if scenic:
            subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                            "-i", f"anullsrc=channel_layout=mono:sample_rate={SAMPLE_RATE}", "-t", f"{s['seconds']:.2f}",
                            "-c:a", "pcm_s16le", str(out)], check=True)
        elif s.get("caption_style") == "native":
            clip, seg = native_by_id[s["segment_ids"][0]]
            native_audio(cfg, clip, seg, out)
        elif mock:
            mock_audio(cfg, s["text"], out, script.get("language", "en"))
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
            raw.write_bytes(sarvam_request(cfg, s["text"], lang))
            trim_and_normalise(cfg, raw, out, lang)
            raw.unlink(missing_ok=True)
        return {"id": s["id"], "path": str(out), "duration": round(wav_duration(out), 3),
                "native": s.get("caption_style") == "native"}

    gap = cfg["tts"].get("gap_seconds", 0.15)
    eleven = cfg["tts"].get("provider") == "elevenlabs" and not mock and not scenic and \
        not any(s.get("caption_style") == "native" for s in script["sentences"])
    if eleven:
        parts = elevenlabs_script(cfg, script, adir)
        gap = 0.0                                      # the natural pauses are already inside each piece
    else:
        workers = 1 if cfg["tts"].get("provider") != "sarvam" else cfg["tts"].get("parallel_requests", 4)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            parts = list(pool.map(one, script["sentences"]))
    if scenic:
        gap = 0.0

    # gentle tempo correction so the finished voiceover lands inside the target length
    lo, hi = (script.get("duration_range") or [0, 10 ** 6])
    gap0 = gap * max(0, len(parts) - 1)
    total0 = sum(p["duration"] for p in parts if not p.get("native")) + gap0 + \
        sum(p["duration"] for p in parts if p.get("native"))
    target = lo + 1.0 if total0 < lo + 1.0 else (hi - 2.0 if total0 > hi - 2.0 else None)
    if scenic:
        target = None                                  # card timings are set by hand
    if target:
        f = max(0.88, min(1.08, total0 / target))          # atempo < 1 slows, > 1 speeds up
        if abs(f - 1) > 0.01:
            for p in parts:
                if p.get("native"):
                    continue
                tmp = Path(p["path"]).with_suffix(".tmp.wav")
                subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-i", p["path"],
                                "-af", f"atempo={f:.3f}", "-c:a", "pcm_s16le", str(tmp)], check=True)
                os.replace(tmp, p["path"])
                p["duration"] = round(wav_duration(p["path"]), 3)
            log("tts", f"tempo x{f:.2f} to fit {lo}-{hi} s (was {total0:.1f} s)")

    # join with a short breath between sentences
    gap_wav = adir / "_gap.wav"
    if gap > 0:
        subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-t", str(gap), "-c:a", "pcm_s16le", str(gap_wav)],
                       check=True)
    lst = adir / "_concat.txt"
    lines = []
    for i, p in enumerate(parts):
        lines.append(f"file '{Path(p['path']).name}'")
        if i < len(parts) - 1 and gap > 0:
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
