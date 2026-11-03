"""clean-run length (s) for shot keys: python runlen.py [plans.json] -> per plan shot, or all keys >= 3 s"""
import json, sys
from pathlib import Path
from common import load_config, read_json
from judge import segment_index
from fit_timeline import clean_run
SP = Path(__file__).parent
cfg = load_config(); cat = read_json(cfg["_paths"]["catalog_file"]); idx = segment_index(cat)
clips = {c["file_id"]: c for c in cat["clips"].values()}
cuts = read_json(cfg["_paths"]["catalog"] / "cuts.json", {})
keys = {}
for f in ("allkeys.json", "sv/keys.json", "oc/keys.json", "wk/keys.json", "oct/keys.json", "k_keys.json"):
    if (SP / "keys" / f).exists():
        keys.update(json.load(open(SP / "keys" / f)))
def rl(k):
    s = idx.get(keys[k]["segment_id"]) if k in keys else None
    if not s: return None
    c = clips[s["file_id"]]; r = clean_run(cuts.get(s["file_id"]), c.get("duration_s") or s["out"], s)
    return round(r[1] - r[0], 2) if r else None
if len(sys.argv) > 1:
    for p in json.load(open(sys.argv[1], encoding="utf-8")):
        print(p["video_title"][:30], [(x, rl(x)) for s in p["sentences"] for x in s["shots"]])
else:
    print(" ".join(f"{k}:{rl(k)}" for k in sorted(keys) if (rl(k) or 0) >= 3))
