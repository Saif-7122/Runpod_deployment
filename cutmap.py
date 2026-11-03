"""Hidden-cut map: many Drive clips are already-edited reels (CapCut exports) with their own cuts every 1-2 s.
A shot that spans one of those cuts flashes a frame of another scene. This scans each clip once (scdet on the
proxy) and stores the cut times in workspace/catalog/cuts.json; fit_timeline keeps every shot inside a clean run.

    python cutmap.py            # all approved clips not scanned yet
"""
import json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from common import load_config, read_json, write_json, ffmpeg_bin, log

THRESHOLD = 14


def scan(cfg, clip):
    src = next((p for p in (clip.get("proxy"), clip.get("local_path")) if p and Path(p).exists()), None)
    if not src:
        return None
    r = subprocess.run([ffmpeg_bin(cfg), "-hide_banner", "-i", src, "-vf", f"scale=240:-2,scdet=threshold={THRESHOLD}",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [round(float(t), 3) for t in re.findall(r"lavfi\.scd\.time: ([\d.]+)", r.stderr)]


def similar_span(src, hero, lo, hi, step=0.2, min_corr=0.6, min_shape=0.3):
    """Seconds around `hero` (within lo..hi) where the picture still looks like the hero frame (HSV histogram
    correlation) and keeps its layout (grey-thumbnail correlation). Catches what scdet misses in pre-edited clips:
    dissolves, whip pans, a camera move to a new subject."""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(src))

    def hist(t):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            return None
        h = cv2.calcHist([cv2.cvtColor(cv2.resize(fr, (96, 170)), cv2.COLOR_BGR2HSV)], [0, 1], None, [24, 16],
                         [0, 180, 0, 256])
        g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (24, 42)).astype(float).ravel()
        return cv2.normalize(h, h).flatten(), g

    def same(x):
        return (x is not None and cv2.compareHist(ref[0], x[0], cv2.HISTCMP_CORREL) >= min_corr
                and float(np.corrcoef(ref[1], x[1])[0, 1]) >= min_shape)

    ref = hist(hero)
    if ref is None:
        return lo, hi
    a = b = hero
    while a - step >= lo:
        if not same(hist(a - step)):
            break
        a -= step
    while b + step <= hi:
        if not same(hist(b + step)):
            break
        b += step
    cap.release()
    return round(a, 2), round(b, 2)


_TEMPLATES = None


def has_burned_logo(src, t, min_score=0.33):
    """True if the Oxygen Forest logo (red box or the flower mark) is already burned into the top-right of the clip at
    second t. Edge-template match over a few scales in the top-right corner of a 1080-wide frame."""
    import cv2
    global _TEMPLATES
    if _TEMPLATES is None:
        root = Path(__file__).resolve().parent / "assets"
        _TEMPLATES = []
        for name in ("of_logo_red.png", "of_logo_flower_tpl.png"):
            img = cv2.imread(str(root / name), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                img = cv2.resize(img, None, fx=0.5, fy=0.5)             # 4K crops -> 1080-wide frame scale
                _TEMPLATES.append(cv2.Canny(img, 30, 90))
    cap = cv2.VideoCapture(str(src))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, fr = cap.read()
    cap.release()
    if not ok:
        return False
    fr = cv2.resize(fr, (1080, int(fr.shape[0] * 1080 / fr.shape[1])))
    corner = fr[0:520, 600:1080]
    # 1) the solid maroon box: one compact, roughly rectangular blob of the brand red
    hsv = cv2.cvtColor(corner, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, (0, 60, 50), (12, 255, 210)) | cv2.inRange(hsv, (165, 60, 50), (180, 255, 210))
    n, _, stats, _ = cv2.connectedComponentsWithStats(red)
    for x, y, w, h, area in stats[1:]:
        if area > 1800 and 0.9 <= h / max(w, 1) <= 1.6 and area / (w * h) > 0.55:
            return True, 1.0
    # 2) the flower mark (pink / orange line logo, no box): edge template match over scales
    roi = cv2.Canny(cv2.cvtColor(corner, cv2.COLOR_BGR2GRAY), 30, 90)
    best = 0.0
    for tpl in _TEMPLATES:
        for s in (0.45, 0.6, 0.75, 0.9, 1.0, 1.15, 1.35, 1.6, 1.85, 2.1):
            tt = cv2.resize(tpl, None, fx=s, fy=s)
            if tt.shape[0] >= roi.shape[0] or tt.shape[1] >= roi.shape[1]:
                continue
            best = max(best, float(cv2.matchTemplate(roi, tt, cv2.TM_CCOEFF_NORMED).max()))
    return best >= min_score, round(best, 3)


def main():
    cfg = load_config()
    cat = read_json(cfg["_paths"]["catalog_file"])["clips"]
    out = cfg["_paths"]["catalog"] / "cuts.json"
    cuts = read_json(out, {})
    todo = [c for c in cat.values() if c.get("segments") and c["file_id"] not in cuts]
    log("cutmap", f"{len(todo)} clips to scan")
    with ThreadPoolExecutor(6) as ex:
        for c, res in zip(todo, ex.map(lambda c: scan(cfg, c), todo)):
            if res is not None:
                cuts[c["file_id"]] = res
    write_json(out, cuts)
    edited = sum(1 for v in cuts.values() if len(v) >= 3)
    log("cutmap", f"{len(cuts)} clips mapped, {edited} look pre-edited (3+ internal cuts)")


if __name__ == "__main__":
    main()
