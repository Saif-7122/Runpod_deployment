"""Make the same script line with every free local voice so you can choose by ear (run on the GPU pod).

  python voice_samples.py            -> workspace/voice_samples/<provider>_<variant>.wav (+ optional Drive upload)
  python voice_samples.py --upload
"""
import argparse
import copy

from common import load_config, log
from local_models import synthesize_local

LINE = ("You know that feeling on a Saturday morning? No traffic, no noise. "
        "Just trees, birds, and your own little forest, two hours from Hyderabad.")

VARIANTS = {
    "chatterbox_natural": ("chatterbox", {"exaggeration": 0.5, "cfg_weight": 0.5}),
    "chatterbox_warm": ("chatterbox", {"exaggeration": 0.65, "cfg_weight": 0.35}),
    "indic_parler_divya": ("indic_parler", {"description": "Divya speaks in a warm, friendly, conversational tone with a slightly fast pace and clear Indian English accent. The recording is very clear with no background noise."}),
    "indic_parler_mary": ("indic_parler", {"description": "Mary speaks in a sweet, expressive, smiling tone at a moderate pace with an Indian English accent. Very clear recording, close to the microphone."}),
    "kokoro_emma": ("kokoro", {"voice": "bf_emma", "lang": "b", "speed": 1.05}),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    base = load_config()
    out = base["_paths"]["workspace"] / "voice_samples"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for name, (prov, opts) in VARIANTS.items():
        cfg = copy.deepcopy(base)
        cfg["tts"]["provider"] = prov
        cfg["tts"][prov] = {**cfg["tts"].get(prov, {}), **opts}
        try:
            path = out / f"{name}.wav"
            synthesize_local(cfg, LINE, path)
            made.append(path)
            log("voices", f"{name}: ok")
        except Exception as e:
            log("voices", f"{name}: FAILED {e}")
    if a.upload and made:
        import drive
        folder = drive.ensure_folder(base["drive"]["output_folder_id"], "voice_samples")
        for p in made:
            drive.upload(p, folder, p.name, "audio/wav")
        log("voices", f"uploaded {len(made)} samples to OUTPUT/voice_samples")


if __name__ == "__main__":
    main()
