"""Judge: the gate between planning (cheap text) and production (voice + render).

Stage 1  rule checks  (free, instant): length 30-40 s, beat order, hook rules, cut lengths, footage validity,
                                       variety, overlay length, banned claims.
Stage 2  scored review (Claude, temperature 0): each dimension has its own minimum, plus a weighted total.
         The reviewer also picks the strongest of the director's 3 hook options.

A plan reaches TTS + render only if it passes BOTH stages (config judge.gate).

  python judge.py --run-dir workspace/runs/<run_id> --brief brief.json
"""
import argparse
import json
import re
from pathlib import Path

import yaml

from common import ask_claude_json, load_config, read_json, write_json
from director import load_style, rubric_text


def words(text):
    return len(re.findall(r"[\w'’-]+", text or ""))


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lakhs": 100000, "crore": 10000000, "crores": 10000000}


def numbers_in(text):
    """All numbers in a text, written as digits ('2,057', '450+') or as words ('four hundred and fifty')."""
    t = (text or "").lower().replace("-", " ")
    nums = set()
    for x, scale in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(thousand|lakhs?|crores?)?", t):
        nums.add(float(x.replace(",", "")) * {"thousand": 1000, "lakh": 100000, "lakhs": 100000,
                                               "crore": 10000000, "crores": 10000000}.get(scale, 1))
    t = re.sub(r"\d[\d,]*(?:\.\d+)?\s*(?:thousand|lakhs?|crores?)?", " ", t)
    total = cur = None
    for w in re.findall(r"[a-z]+", t) + ["."]:
        if w in _UNITS or w in _TENS:
            cur = (cur or 0) + _UNITS.get(w, _TENS.get(w, 0))
        elif w in _SCALES and (cur is not None or total is not None):
            if _SCALES[w] == 100:
                cur = (cur or 1) * 100
            else:
                total = (total or 0) + (cur or 1) * _SCALES[w]
                cur = None
        elif w == "and" and (cur is not None or total is not None):
            continue
        else:
            if cur is not None or total is not None:
                nums.add(float((total or 0) + (cur or 0)))
            total = cur = None
    return nums


def unsupported_numbers(script, brief):
    """Numbers in the script that do not appear anywhere in the brief's facts (0, 1, 2 are always allowed)."""
    allowed = set()
    for v in list((brief.get("facts") or {}).values()) + brief.get("key_value_propositions", []) + \
            brief.get("taglines_from_site", []) + [brief.get("call_to_action", "")]:
        allowed |= numbers_in(str(v))
    allowed |= {n * k for n in list(allowed) for k in (100000,) if n < 1000}   # "70 lakhs" = 7,000,000
    bad = []
    for s in script.get("sentences", []):
        for n in numbers_in(s["text"] + " " + s.get("overlay", "")):
            if n > 2 and n not in allowed:
                bad.append(f"{s['id']}: number {n:g} is not in the brief's facts")
    return bad


def segment_index(catalog):
    idx = {}
    for c in catalog.get("clips", {}).values():
        for s in c.get("segments", []):
            if "segment_id" in s:
                idx[s["segment_id"]] = {**s, "file_id": c["file_id"], "clip_name": c["name"]}
    return idx


def native(s):
    return s.get("caption_style") == "native" or bool(s.get("native_segment_id"))


def spoken_seconds(cfg, script, segs):
    from director import wps_for
    wps = wps_for(cfg, script)
    return sum(segs.get(s["segment_ids"][0], {}).get("usable_s", 0) if native(s) and s.get("segment_ids")
               else words(s["text"]) / wps for s in script.get("sentences", []))


def rule_checks(cfg, script, catalog, style=None, brief=None):
    from director import wps_for
    d, v = cfg["director"], []
    if brief:
        v += unsupported_numbers(script, brief)
    wps, max_scene = wps_for(cfg, script), d["max_scene_seconds"]
    sents = script.get("sentences", [])
    segs = segment_index(catalog)
    if not sents:
        return ["script has no sentences"]

    lo, hi = script.get("duration_range") or [script["target_seconds"] * 0.85, script["target_seconds"] * 1.15]
    est = spoken_seconds(cfg, script, segs)
    if not (lo - 1 <= est <= hi + 1):
        v.append(f"length: about {est:.0f} s spoken, must be {lo}-{hi} s "
                 f"({'add' if est < lo else 'cut'} about {abs(round((lo if est < lo else hi) - est) * wps):.0f} words)")

    # beat order (style structure)
    if style:
        order = [b["beat"] for b in style["structure"]]
        seen_beats = [s.get("beat") for s in sents]
        missing = [b for b in order if b not in seen_beats]
        if missing:
            v.append(f"missing beats: {', '.join(missing)}")
        idx = [order.index(b) for b in seen_beats if b in order]
        if idx != sorted(idx):
            v.append(f"beats out of order: {' > '.join(str(b) for b in seen_beats)} (expected {' > '.join(order)})")

    hook = sents[0]
    if not native(hook):
        if words(hook["text"]) > 12:
            v.append(f"hook too long: {words(hook['text'])} words (max 12)")
        low = (hook["text"] + " " + hook.get("overlay", "")).lower()
        if any(k in low for k in ("₹", "lakh", "price", "oxygen forest")):
            v.append("hook must not lead with price or the brand name (save them for later beats)")
    n_native = sum(1 for s in sents if native(s))
    if n_native > d.get("max_native_per_video", 1):
        v.append(f"{n_native} own-audio clips used (max {d.get('max_native_per_video', 1)})")
    if sents[-1].get("caption_style") != "cta" and sents[-1].get("beat") != "cta":
        v.append("last line must be the CTA")
    overlays = [s for s in sents if s.get("overlay")]
    if len(overlays) > (len(sents) + 1) // 2 + 1:
        v.append(f"too many overlays ({len(overlays)} for {len(sents)} lines): let shots breathe")

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
        if len(s.get("overlay", "").split()) > 5:
            v.append(f"{s['id']}: overlay over 5 words")
        for sid in ids:
            seg = segs.get(sid)
            if not seg:
                v.append(f"{s['id']}: unknown segment {sid}")
                continue
            if seg.get("native_audio"):
                v.append(f"{s['id']}: {sid} has its own audio; use it as a native_segment_id line")
            if seg.get("status") != "approved":
                v.append(f"{s['id']}: segment {sid} is not approved")
            if sid in seen:
                v.append(f"{s['id']}: segment {sid} used twice")
            seen.add(sid)
            if seg.get("usable_s", 0) + 0.25 < share:
                v.append(f"{s['id']}: segment {sid} has {seg.get('usable_s')} s, needs {share:.1f} s")
            if prev and prev["file_id"] == seg["file_id"]:
                v.append(f"{s['id']}: {sid} comes from the same clip as the previous cut")
            prev = seg

    text = " ".join((s["text"] + " " + s.get("overlay", "")) for s in sents).lower()
    for claim in cfg.get("banned_claims", []):
        if claim.lower() in text:
            v.append(f"banned claim: '{claim}'")
    return v


JUDGE_SYSTEM = """You are the final reviewer at a performance-marketing studio. You decide whether a planned 9:16 Reel is good enough to spend production money on and run as a Meta lead ad.
You did not write it. Score strictly and consistently: most first drafts should NOT pass. A score of 8/10 on a dimension means "a senior editor would ship this part as is".

Style pack:
{style}

Brand rubric:
{rubric}

Reply with JSON only."""

DIMENSIONS = {
    "hook": "First 1-3 s: would a scrolling viewer in the target audience stop? Motion-led shot + a line about their life or a vivid image. Specific beats generic.",
    "storyboard": "Every line's footage visibly shows what is said; beats flow hook > context > main > proof > payoff > cta; follows the style editing_rules (hook opens on motion, pacing curve fast-breathe-calm, wide>medium>close, the named thing is on screen when said, payoff on faces, calm wide CTA); pacing suits 30-40 s.",
    "content": "One clear core idea; answers the audience's real objection; conversational, natural spoken English (not ad-speak, not a news reader); specific facts.",
    "cta": "One clear, low-friction next step that fits a lead ad; motivated by what came before.",
}


def scored_review(cfg, brief, plan, catalog, style):
    segs = segment_index(catalog)
    lines = []
    for s in plan["sentences"]:
        item = {"id": s["id"], "beat": s.get("beat"), "line": s["text"], "overlay": s.get("overlay", ""),
                "footage": [f"{sid}: {segs.get(sid, {}).get('description', '?')}" for sid in s.get("segment_ids", [])]}
        if native(s):
            item["note"] = "plays the clip's own recorded audio, not the voiceover"
        lines.append(item)
    hooks = [{"index": i, "line": h.get("line"), "footage": segs.get(h.get("segment_id"), {}).get("description", "?")}
             for i, h in enumerate(plan.get("hook_options", []))]
    dims = "\n".join(f'- {k}: {v}' for k, v in DIMENSIONS.items())
    content = f"""BRIEF AND FACTS
{json.dumps(brief, indent=2, ensure_ascii=False)}

CORE IDEA: {plan.get('core_idea')}
ANGLE: {plan.get('angle')}

PLAN (storyboard: each line with the footage under it)
{json.dumps(lines, indent=2, ensure_ascii=False)}

HOOK OPTIONS (the plan currently uses option 0 unless noted)
{json.dumps(hooks, indent=2, ensure_ascii=False)}

Score 0-10 on each dimension:
{dims}

Also:
- facts: list every claim that is NOT supported by the brief's facts (empty list if none).
- best_hook_index: which hook option is strongest for this audience (0-2).
- fixes: the 1-4 most important concrete changes, each naming the line id.

Return JSON:
{{"scores": {{"hook": <0-10>, "storyboard": <0-10>, "content": <0-10>, "cta": <0-10>}},
  "unsupported_claims": ["..."],
  "best_hook_index": <int>,
  "fixes": ["s03: ...", "..."],
  "summary": "<one line>"}}"""
    return ask_claude_json(cfg, "judge_model",
                           JUDGE_SYSTEM.format(style=yaml.safe_dump(style, allow_unicode=True, sort_keys=False),
                                               rubric=rubric_text()),
                           content, temperature=0)


def gate(cfg, scores, unsupported):
    g = cfg["judge"]["gate"]
    w = g["weights"]
    total = round(sum(scores.get(k, 0) * w[k] for k in w) / sum(w.values()) * 10)
    fails = [f"{k} {scores.get(k, 0)}/10 < {g['min'][k]}" for k in g["min"] if scores.get(k, 0) < g["min"][k]]
    if total < g["min_total"]:
        fails.append(f"total {total} < {g['min_total']}")
    if unsupported:
        fails.append("unsupported claims: " + "; ".join(unsupported))
    return total, fails


def judge(cfg, brief, plan, catalog, style=None):
    style = style or load_style(plan.get("style") or cfg["director"].get("default_style", "weekend_home"))
    violations = rule_checks(cfg, plan, catalog, style)
    result = {"rule_violations": violations, "review": None, "score": 0, "passed": False, "gate_fails": []}
    if violations:
        # mechanical problems are fixed by a rewrite before paying for a review
        result["feedback"] = violations
        return result
    rev = scored_review(cfg, brief, plan, catalog, style)
    scores = rev.get("scores", {})
    total, fails = gate(cfg, scores, rev.get("unsupported_claims", []))
    result.update(review=rev, score=total, gate_fails=fails, passed=not fails,
                  best_hook_index=rev.get("best_hook_index", 0),
                  feedback=fails + rev.get("fixes", []))
    return result


def rank_candidates(cfg, brief, plans, catalog, style):
    """ONE cheap call (Haiku) scores every candidate on the same 4 dimensions + unsupported claims.
    Returns plans sorted best-first, each with .verdict {scores, score, passed, gate_fails, fixes}."""
    segs = segment_index(catalog)
    show = []
    for k, p in enumerate(plans):
        show.append({"candidate": k, "core_idea": p.get("core_idea"),
                     "lines": [{"beat": s.get("beat"), "line": s["text"], "overlay": s.get("overlay", ""),
                                "footage": [segs.get(x, {}).get("description", "?")[:90] for x in s.get("segment_ids", [])],
                                **({"own_audio": True} if native(s) else {})} for s in p["sentences"]]})
    dims = "\n".join(f"- {k}: {v}" for k, v in DIMENSIONS.items())
    lang = plans[0].get("language", "en") if plans else "en"
    lang_name = {"te": "Telugu", "hi": "Hindi"}.get(lang)
    content = f"""LANGUAGE OF THE SCRIPTS: {f"{lang_name} - also judge how natural and conversational the {lang_name} sounds" if lang_name else "English"}

FACTS ALLOWED (anything else is unsupported)
{json.dumps(brief.get('facts', {}), ensure_ascii=False)}
CTA: {brief.get('call_to_action')}

CANDIDATES
{json.dumps(show, ensure_ascii=False)}

Score EVERY candidate 0-10 on:
{dims}
Return JSON: {{"results": [{{"candidate": <int>, "scores": {{"hook": 0, "storyboard": 0, "content": 0, "cta": 0}},
  "unsupported_claims": ["..."], "fixes": ["s03: ..."]}}]}}"""
    score = {"type": "integer", "minimum": 0, "maximum": 10}
    schema = {"type": "object", "required": ["results"], "properties": {"results": {
        "type": "array", "minItems": len(plans), "maxItems": len(plans), "items": {
            "type": "object", "required": ["candidate", "scores", "unsupported_claims", "fixes"],
            "properties": {
                "candidate": {"type": "integer", "minimum": 0, "maximum": len(plans) - 1},
                "scores": {"type": "object", "required": list(DIMENSIONS),
                           "properties": {k: score for k in DIMENSIONS}},
                "unsupported_claims": {"type": "array", "items": {"type": "string"}},
                "fixes": {"type": "array", "maxItems": 4, "items": {"type": "string"}}}}}}}
    data = ask_claude_json(cfg, "judge_model",
                           JUDGE_SYSTEM.format(style=yaml.safe_dump(style, allow_unicode=True, sort_keys=False),
                                               rubric=rubric_text()), content, schema=schema)
    by = {r.get("candidate"): r for r in data.get("results", [])}
    for k, p in enumerate(plans):
        r = by.get(k, {})
        scores = r.get("scores", {})
        total, fails = gate(cfg, scores, r.get("unsupported_claims", []))
        p["verdict"] = {"scores": scores, "score": total, "passed": not fails, "gate_fails": fails,
                        "fixes": r.get("fixes", []), "rule_violations": []}
    return sorted(plans, key=lambda p: (p["verdict"]["passed"], p["verdict"]["score"]), reverse=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--brief", default="brief.json")
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    run = Path(a.run_dir)
    res = judge(cfg, read_json(a.brief), read_json(run / "plan.json"),
                read_json(cfg["_paths"]["catalog_file"], {"clips": {}}))
    write_json(run / "judge_cli.json", res)
    print(json.dumps({"score": res["score"], "passed": res["passed"], "feedback": res["feedback"]}))
