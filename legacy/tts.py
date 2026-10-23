import os
import sys
import json
import argparse
import subprocess
import wave
import contextlib
import urllib.request
import yaml

def load_yaml(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def get_audio_duration(file_path):
    # Try using wave module
    try:
        with contextlib.closing(wave.open(file_path, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except Exception:
        pass

    # Fallback to ffprobe
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 20.0

def generate_tts(run_dir, config_path="config.yaml", custom_text=None):
    config = load_yaml(config_path)
    tts_conf = config.get("tts", {})
    voice = tts_conf.get("voice", "meera")
    lang = tts_conf.get("language_code", "en-IN")
    pace = tts_conf.get("pace", 1.05)
    model = tts_conf.get("model", "bulbul:v1")

    os.makedirs(run_dir, exist_ok=True)
    raw_audio_path = os.path.join(run_dir, "raw_tts.wav")
    clean_audio_path = os.path.join(run_dir, "clean_audio.wav")
    timeline_path = os.path.join(run_dir, "timeline.json")

    voiceover_text = custom_text
    if not voiceover_text and os.path.exists(timeline_path):
        try:
            with open(timeline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                voiceover_text = data.get("voiceover_script", "")
        except Exception:
            pass

    if not voiceover_text:
        voiceover_text = "Experience pure living at Oxygen Forest. Claim your private sanctuary today."

    sarvam_key = os.environ.get("SARVAM_API_KEY")

    audio_bytes = None
    if sarvam_key:
        print(f"[TTS] Requesting Sarvam AI TTS (voice: {voice}, pace: {pace})...", file=sys.stderr)
        try:
            payload = json.dumps({
                "inputs": [voiceover_text],
                "target_language_code": lang,
                "speaker": voice,
                "pace": pace,
                "model": model
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.sarvam.ai/text-to-speech",
                data=payload,
                headers={
                    "api-subscription-key": sarvam_key,
                    "content-type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                import base64
                audio_base64 = resp_json["audios"][0]
                audio_bytes = base64.b64decode(audio_base64)
        except Exception as e:
            print(f"[TTS] Warning: Sarvam API call failed: {e}", file=sys.stderr)

    # If no audio generated from API, generate synthetic WAV for testing
    if not audio_bytes:
        print("[TTS] Generating local baseline WAV test tone...", file=sys.stderr)
        cmd_gen = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=18",
            "-ar", "44100", "-ac", "2", raw_audio_path
        ]
        subprocess.run(cmd_gen, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        with open(raw_audio_path, "wb") as f:
            f.write(audio_bytes)

    # Run auto-editor on raw_tts.wav
    active_audio = raw_audio_path
    if os.path.exists(raw_audio_path) and os.path.getsize(raw_audio_path) > 0:
        print(f"[TTS] Running auto-editor on {raw_audio_path}...", file=sys.stderr)
        auto_cmd = ["auto-editor", raw_audio_path, "-o", clean_audio_path, "--margin", "0.1sec"]
        subprocess.run(auto_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if os.path.exists(clean_audio_path) and os.path.getsize(clean_audio_path) > 0:
            active_audio = clean_audio_path
            print(f"[TTS] Auto-editor cleaned audio generated: {clean_audio_path}", file=sys.stderr)
        else:
            print(f"[TTS] Clean audio not generated, falling back to {raw_audio_path}", file=sys.stderr)

    duration = get_audio_duration(active_audio)

    meta = {
        "audio_file": os.path.basename(active_audio),
        "full_path": active_audio,
        "duration_seconds": round(duration, 3),
        "text": voiceover_text
    }

    with open(os.path.join(run_dir, "audio_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    sys.stdout.flush()
    print(json.dumps({"status": "success", "audio_path": active_audio, "duration": round(duration, 3)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TTS Audio Generator & Auto-Editor Processor")
    parser.add_argument("--run-dir", required=True, help="Run directory path")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--text", default=None, help="Optional direct voiceover script text")
    args = parser.parse_args()

    generate_tts(run_dir=args.run_dir, config_path=args.config, custom_text=args.text)
