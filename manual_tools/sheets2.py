"""One tile per clip (frame from its longest approved segment) for the given projects; keys cNNN_k per segment.
   python sheets2.py <out_dir> <prefix> "<project>" ["<project>" ...]  -> sheet_*.jpg + keys.json"""
import json, subprocess, sys
from pathlib import Path
import cv2, numpy as np
from common import load_config, read_json, ffmpeg_bin

cfg = load_config()
cat = read_json(cfg["_paths"]["catalog_file"])["clips"]
out, prefix, projects = Path(sys.argv[1]), sys.argv[2], set(sys.argv[3:])
out.mkdir(parents=True, exist_ok=True)
keys, tiles, n = {}, [], 0
for c in cat.values():
    if c["project"] not in projects:
        continue
    segs = [s for s in c.get("segments", []) if s.get("status") == "approved" and not s.get("native_audio")]
    src = next((p for p in (c.get("proxy"), c.get("local_path")) if p and Path(p).exists()), None)
    if not segs or not src:
        continue
    ck = f"{prefix}{n:03d}"; n += 1
    for k, s in enumerate(sorted(segs, key=lambda s: s["in"])):
        keys[f"{ck}_{k}"] = {"segment_id": s["segment_id"], "usable_s": s["usable_s"], "file": c["file_id"][:6], "clip": c["name"]}
    best = max(segs, key=lambda s: s["usable_s"])
    t = best.get("hero_second") or (best["in"] + best["out"]) / 2
    r = subprocess.run([ffmpeg_bin(cfg), "-loglevel", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                        "-vf", "scale=320:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
    if img is None:
        img = np.zeros((180, 320, 3), np.uint8)
    img = cv2.resize(img, (320, 180) if img.shape[1] > img.shape[0] else (101, 180))
    tile = np.zeros((200, 320, 3), np.uint8); x0 = (320 - img.shape[1]) // 2
    tile[:180, x0:x0 + img.shape[1]] = img
    tot = sum(s["usable_s"] for s in segs)
    cv2.putText(tile, f"{ck} x{len(segs)} {tot:.0f}s", (4, 196), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    tiles.append(tile)
for i in range(0, len(tiles), 24):
    group = tiles[i:i + 24] + [np.zeros((200, 320, 3), np.uint8)] * (24 - len(tiles[i:i + 24]))
    rows = [np.hstack(group[r * 6:(r + 1) * 6]) for r in range(4)]
    cv2.imwrite(str(out / f"sheet_{i // 24 + 1:02d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])
json.dump(keys, open(out / "keys.json", "w"), indent=0)
print(n, "clips,", len(keys), "segments,", (len(tiles) + 23) // 24, "sheets")
