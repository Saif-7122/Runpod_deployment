"""Judge: free rule checks first, then a Claude rubric review. Pass = no rule violations and rubric >= threshold.

  python judge.py --run-dir workspace/runs/<run_id> --brief brief.json
"""
import argparse
import json
import re
from pathlib import Path

from common import ask_claude_json, load_config, read_json, write_json
from director import rubric_text


def words(text):
    return len(re.findall(r"[\w'’-]+", text or ""))


def segment_index(catalog):
    idx = {}
    for c in catalog.get("clips", {}).values():
        for s in c.get("segments", []):
            if "segment_id" in s:
                idx[s["segment_id"]] = {**s, "file_id": c["file_id"], "clip_name": c["name"]}
    return idx


def rule_checks(cfg, script, catalog):
    d, v = cfg["director"], []
    wps, max_scene = d["words_per_second"], d["max_scene_seconds"]
    sents = script.get("sentences", [])
    segs = segment_index(catalog)
    if not sents:
        return ["script has no sentences"]

    def native(s):
        return s.get("caption_style") == "native" or bool(s.get("native_segment_id"))

    est = sum(segs.get(s["segment_ids"][0], {}).get("usable_s", 0) if native(s) and s.get("segment_ids")
              else words(s["text"]) / wps for s in sents)
    target = script["target_seconds"]
    tol = cfg["judge"]["length_tolerance"]
    if abs(est - target) > tol * target:
        v.append(f"length: about {est:.0f} s spoken, target {target:.0f} s (±{tol:.0%})")
    if not native(sents[0]) and words(sents[0]["text"]) > 12:
        v.append(f"hook too long: sentence 1 has {words(sents[0]['text'])} words (max 12)")
    n_native = sum(1 for s in sents if native(s))
    if n_native > d.get("max_native_per_video", 1):
        v.append(f"{n_native} own-audio clips used (max {d.get('max_native_per_video', 1)})")
    if sents[-1].get("caption_style") != "cta":
        v.append("last sentence must be the CTA (caption_style 'cta')")

    seen, prev = set(), None
    for s in sents:
        ids = s.get("segment_ids") or []
        if not ids:
            v.append(f"{s['id']}: no segment")
            continue
        if native(s):
            seg = segs.get(ids[0])
            if not seg or not seg.get("native_audio") or seg.get("status") != "approved":
                v.append(f"{s['id']}: {ids[0]} is not an approved own-audio clip")
            else:
                if ids[0] in seen:
                    v.append(f"{s['id']}: {ids[0]} used twice")
                seen.add(ids[0])
                prev = seg
            continue
        share = words(s["text"]) / wps / len(ids)
        if share > max_scene + 0.3:
            v.append(f"{s['id']}: {share:.1f} s per cut (max {max_scene}); add a segment or shorten the line")
        if len(s.get("overlay", "").split()) > 6:
            v.append(f"{s['id']}: overlay over 6 words")
        for sid in ids:
            seg = segs.get(sid)
            if not seg:
                v.append(f"{s['id']}: unknown segment {sid}")
                continue
            if seg.get("native_audio"):
                v.append(f"{s['id']}: {sid} has its own audio; use it as a native_segment_id line, not under the voiceover")
            if seg.get("status") != "approved":
                v.append(f"{s['id']}: segment {sid} is not approved")
            if sid in seen:
                v.append(f"{s['id']}: segment {sid} used twice")
            seen.add(sid)
            if seg.get("usable_s", 0) + 0.25 < share:
                v.append(f"{s['id']}: segment {sid} has {seg.get('usable_s')} s, needs {share:.1f} s")
            if prev:
                if prev["file_id"] == seg["file_id"]:
                    v.append(f"{s['id']}: {sid} comes from the same clip as the previous cut")
                elif (prev.get("shot_type"), prev.get("camera_move")) == (seg.get("shot_type"), seg.get("camera_move")):
                    v.append(f"{s['id']}: {sid} repeats the previous shot type and camera move")
            prev = seg

    text = " ".join((s["text"] + " " + s.get("overlay", "")) for s in sents).lower()
    for claim in cfg.get("banned_claims", []):
        if claim.lower() in text:
            v.append(f"banned claim: '{claim}'")
    return v


JUDGE_SYSTEM = """You are a strict reviewer of short-form real-estate video ads. You score scripts against the brand rubric below.
You did not write the script. Be critical: 80+ means ready to publish with paid budget behind it.

{rubric}

Reply with JSON only."""


def rubric_review(cfg, brief, script, catalog):
    segs = segment_index(catalog)
    shown = []
    for s in script["sentences"]:
        shots = [f"{sid}: {segs.get(sid, {}).get('description', '?')}" for sid in s.get("segment_ids", [])]
        item = {"id": s["id"], "line": s["text"], "overlay": s.get("overlay", ""), "footage": shots}
        if s.get("caption_style") == "native":
            item["note"] = "plays the clip's own recorded audio (testimonial/presenter), not the voiceover"
        shown.append(item)
    content = f"""BRIEF
{json.dumps(brief, indent=2, ensure_ascii=False)}

SCRIPT (each line with the footage shown under it)
{json.dumps(shown, indent=2, ensure_ascii=False)}

Score each rubric pillar. Also check that every line's footage really shows what the line says.
Return JSON:
{{"pillars": [{{"name": "<pillar>", "score": <int>, "max": <int>, "fix": "<one concrete fix, or empty>"}}],
  "total": <int 0-100>,
  "summary": "<one line>"}}"""
    return ask_claude_json(cfg, "judge_model", JUDGE_SYSTEM.format(rubric=rubric_text()), content, max_tokens=2000)


def judge(cfg, brief, script, catalog):
    violations = rule_checks(cfg, script, catalog)
    result = {"rule_violations": violations, "rubric": None, "score": 0, "passed": False}
    if violations and cfg["judge"].get("skip_rubric_on_rule_fail", True):
        result["feedback"] = violations
        return result
    rub = rubric_review(cfg, brief, script, catalog)
    result["rubric"] = rub
    result["score"] = int(rub.get("total", 0))
    result["passed"] = not violations and result["score"] >= cfg["judge"]["min_score"]
    result["feedback"] = violations + [f"{p['name']}: {p['fix']}" for p in rub.get("pillars", []) if p.get("fix")]
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--brief", default="brief.json")
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    run = Path(a.run_dir)
    res = judge(cfg, read_json(a.brief), read_json(run / "script.json"),
                read_json(cfg["_paths"]["catalog_file"], {"clips": {}}))
    write_json(run / "judge_cli.json", res)
    print(json.dumps({"score": res["score"], "passed": res["passed"], "feedback": res["feedback"]}))
