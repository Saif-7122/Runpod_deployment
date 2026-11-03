"""Shows every chosen shot per line, labelled ON the frame: python verify.py plans.json out_dir"""
import json, subprocess, sys
from pathlib import Path
import cv2, numpy as np
from common import load_config, read_json, ffmpeg_bin
from judge import segment_index

SP = Path(__file__).parent
cfg = load_config()
cat = read_json(cfg["_paths"]["catalog_file"])
idx = segment_index(cat)
clips = {c["file_id"]: c for c in cat["clips"].values()}
keys = {}
for f in ("allkeys.json", "sv/keys.json", "oc/keys.json", "wk/keys.json", "oct/keys.json", "k_keys.json"):
    if (SP / "keys" / f).exists():
        keys.update(json.load(open(SP / "keys" / f)))
out = Path(sys.argv[2]); out.mkdir(exist_ok=True)


def frame(k):
    if k not in keys:                    # clip key -> its longest segment (what make_runs picks)
        k = max((x for x in keys if x.split("_")[0] == k), key=lambda x: keys[x]["usable_s"])
    s = idx[keys[k]["segment_id"]]; c = clips[s["file_id"]]
    src = next(p for p in (c.get("proxy"), c.get("local_path")) if p and Path(p).exists())
    t = s.get("hero_second") or (s["in"] + s["out"]) / 2
    r = subprocess.run([ffmpeg_bin(cfg), "-loglevel", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf",
                        "scale=135:240", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
    cv2.rectangle(img, (0, 0), (135, 22), (0, 0, 0), -1)
    cv2.putText(img, k, (3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    return img


for n, p in enumerate(json.load(open(sys.argv[1], encoding="utf-8"))):
    rows = []
    for s in p["sentences"]:
        tiles = [frame(k) for k in s["shots"]]
        row = np.hstack(tiles + [np.zeros((240, 135, 3), np.uint8)] * (4 - len(tiles)))
        bar = np.zeros((240, 560, 3), np.uint8)
        cv2.putText(bar, f"{s['beat']}", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        rows.append(np.hstack([row, bar]))
    cv2.imwrite(str(out / f"reel{n + 1}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
print("ok")
