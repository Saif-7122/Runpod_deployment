"""One tile per SEGMENT (its hero/middle frame), labelled with its key, 10x4 per sheet.
   python shots.py <out_dir> <keys.json> [<keys.json> ...]"""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2, numpy as np
from common import load_config, read_json, ffmpeg_bin
from judge import segment_index

cfg = load_config()
cat = read_json(cfg["_paths"]["catalog_file"])
idx = segment_index(cat)
clips = {c["file_id"]: c for c in cat["clips"].values()}
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
keys = {}
for f in sys.argv[2:]:
    keys.update(json.load(open(f)))
banned = {k for k in keys if k[0] == "d" and "_" not in k and (int(k[1:]) <= 28 or 42 <= int(k[1:]) <= 75 or k == "d38")}
items = [(k, idx[v["segment_id"]]) for k, v in keys.items() if v["segment_id"] in idx and k not in banned]


def tile(item):
    k, s = item
    c = clips[s["file_id"]]
    src = next((p for p in (c.get("proxy"), c.get("local_path")) if p and Path(p).exists()), None)
    t = s.get("hero_second") or (s["in"] + s["out"]) / 2
    r = subprocess.run([ffmpeg_bin(cfg), "-loglevel", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                        "-vf", "scale=-2:300", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True) if src else None
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r and r.stdout else None
    img = np.zeros((300, 169, 3), np.uint8) if img is None else img
    img = cv2.resize(img, (169, 300))
    tl = np.zeros((320, 169, 3), np.uint8); tl[:300] = img
    cv2.putText(tl, f"{k} {s['usable_s']:.1f}", (2, 315), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    return tl


with ThreadPoolExecutor(8) as ex:
    tiles = list(ex.map(tile, items))
for i in range(0, len(tiles), 40):
    g = tiles[i:i + 40] + [np.zeros((320, 169, 3), np.uint8)] * (40 - len(tiles[i:i + 40]))
    cv2.imwrite(str(out / f"s{i // 40 + 1:02d}.jpg"), np.vstack([np.hstack(g[r * 10:(r + 1) * 10]) for r in range(4)]),
                [cv2.IMWRITE_JPEG_QUALITY, 85])
print(len(tiles), "shots,", (len(tiles) + 39) // 40, "sheets")
