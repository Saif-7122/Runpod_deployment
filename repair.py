"""Free, deterministic fixes for mechanical plan problems (saves a paid rewrite).

Fixes: unknown / duplicate shots, cuts longer than max_scene, shots too short for their share,
back-to-back cuts from the same clip, invalid own-audio lines, too-long or too many overlays.
Cannot fix (left to the rule check / judge): wrong length, missing beats, hook leading with price/brand.
"""
from judge import native, segment_index, words


def repair(cfg, plan, catalog, segs_pool):
    d = cfg["director"]
    from director import wps_for
    wps, max_scene = wps_for(cfg, plan), d["max_scene_seconds"]
    idx = segment_index(catalog)
    pool = [s for s in segs_pool if not s.get("native_audio")]
    used, fixes = set(), []

    def pick(need_s, avoid_files):
        for s in sorted(pool, key=lambda x: (-x.get("ad_score", 0), -x.get("usable_s", 0))):
            if s["segment_id"] in used or s["file_id"] in avoid_files:
                continue
            if s.get("usable_s", 0) + 0.25 >= need_s:
                return s["segment_id"]
        return None

    prev_file = None
    sents = plan.get("sentences", [])
    for k, sent in enumerate(sents):
        ids = list(sent.get("segment_ids") or [])
        if native(sent):
            seg = idx.get(ids[0]) if ids else None
            if seg and seg.get("native_audio") and seg.get("status") == "approved" and ids[0] not in used:
                used.add(ids[0])
                prev_file = seg["file_id"]
                continue
            sent.pop("native_segment_id", None)
            sent["caption_style"] = "normal"
            ids = []
            fixes.append(f"{sent['id']}: invalid own-audio clip -> voiceover line")
        # drop unknown / duplicate / unapproved shots
        clean = []
        for sid in ids:
            seg = idx.get(sid)
            if not seg or seg.get("native_audio") or seg.get("status") != "approved" or sid in used or sid in clean:
                fixes.append(f"{sent['id']}: replaced bad shot {sid}")
                continue
            clean.append(sid)
        # enough shots so every cut <= max_scene and each shot covers its share
        dur = max(0.5, words(sent["text"]) / wps)
        while True:
            n = max(1, len(clean))
            share = dur / n
            short = [sid for sid in clean if idx[sid].get("usable_s", 0) + 0.25 < share]
            if clean and share <= max_scene + 0.3 and not short:
                break
            if len(clean) >= 4:
                break
            avoid = {prev_file} | {idx[x]["file_id"] for x in clean}
            new = pick(min(dur / (n + (1 if clean else 0)), max_scene), avoid)
            if not new:
                break
            clean.append(new)
            used.add(new)
            fixes.append(f"{sent['id']}: added shot {new} (cut length)")
        # back-to-back from the same clip
        for j, sid in enumerate(clean):
            before = prev_file if j == 0 else idx[clean[j - 1]]["file_id"]
            if idx[sid]["file_id"] == before:
                alt = pick(dur / len(clean), {before} | {idx[x]["file_id"] for x in clean})
                if alt:
                    fixes.append(f"{sent['id']}: {sid} swapped for {alt} (same clip twice)")
                    clean[j] = alt
                    used.add(alt)
        used.update(clean)
        sent["segment_ids"] = clean
        if clean:
            prev_file = idx[clean[-1]]["file_id"]
        # overlays
        ov = sent.get("overlay", "") or ""
        if len(ov.split()) > 5:
            sent["overlay"] = ""
            fixes.append(f"{sent['id']}: overlay too long, removed")
    # too many overlays: keep hook, cta and every other one
    with_ov = [s for s in sents if s.get("overlay")]
    limit = (len(sents) + 1) // 2 + 1
    if len(with_ov) > limit:
        keep = {id(sents[0]), id(sents[-1])}
        kept = 0
        for s in with_ov:
            if id(s) in keep or kept < limit - 2:
                kept += 0 if id(s) in keep else 1
                continue
            s["overlay"] = ""
        fixes.append("too many overlays, trimmed")
    if sents:
        sents[-1]["caption_style"] = "cta"
        if sents[0].get("caption_style") != "native":
            sents[0]["caption_style"] = "hook"
    plan["auto_fixes"] = fixes
    return plan
