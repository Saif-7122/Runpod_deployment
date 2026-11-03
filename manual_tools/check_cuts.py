"""Hidden-cut check: for every shot in a run's timeline, scan the exact source window that gets rendered.
   python check_cuts.py <run_dir> [...]   -> prints shots whose window contains a scene change (score >= 14)"""
import json, re, subprocess, sys
from pathlib import Path
from common import load_config, ffmpeg_bin

cfg = load_config()
xf = float(cfg["rendering"].get("transition_seconds", 0))
for rd in sys.argv[1:]:
    tl = json.load(open(Path(rd) / "timeline.json", encoding="utf-8"))
    print("==", Path(rd).name)
    for sc in tl["timeline"]:
        dur = sc["duration"] - sc["hold_seconds"] + xf
        r = subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-ss", f"{sc['source_in']:.3f}", "-t", f"{dur:.3f}",
                            "-i", sc["source_path"], "-vf", "scale=240:-2,scdet=threshold=14", "-an", "-f", "null", "-"],
                           capture_output=True, text=True)
        hits = [(float(t), float(s)) for s, t in re.findall(r"lavfi\.scd\.score: ([\d.]+), lavfi\.scd\.time: ([\d.]+)", r.stderr)]
        flag = "CUT" if hits else "ok "
        print(f"  {flag} scene {sc['scene']:2d} {sc['sentence']} {sc['clip_name'][:28]:28} in={sc['source_in']:.2f} "
              f"dur={dur:.2f} hold={sc['hold_seconds']:.2f} {hits[:3]}")
