"""Director: follows the 10-step pre-production process and writes a full plan (no times, no rendering).

Steps 1-3  brief, objective, audience       -> from brief.json + the style pack (restated in "brief_check")
Step 4     references                        -> the style pack's proven patterns (cited in "references_applied")
Step 5     core idea + angle                 -> one sentence, one idea
Step 6     script                            -> hook, context, main, proof, payoff, cta (3 hook options)
Step 7     storyboard                        -> every line carries its beat, purpose, visual, overlay, transition
Step 8     shot list                         -> each needed shot marked available (segment id) or missing
Step 9     specs                             -> fixed by the style pack + config (9:16, 30-40 s, brand type)
Step 10    review                            -> facts used / risks; then the judge scores the plan

  python director.py --brief brief.json --style weekend_home --run-dir workspace/runs/test
"""
import argparse
import json
from pathlib import Path

import yaml

from common import ROOT, ask_claude_json, load_config, log, read_json, write_json


# ------------------------------------------------------------------ inputs

def load_style(name):
    p = ROOT / "styles" / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"style pack not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def approved_segments(cfg, catalog, project=None, limit=None):
    segs = []
    for c in catalog.get("clips", {}).values():
        where = f"{c.get('project', '')}/{c.get('drive_path', '')}".lower()
        if project and project.lower() not in where:      # folder names don't need to be tidy
            continue
        for s in c.get("segments", []):
            if s.get("status") == "approved":
                segs.append({**s, "file_id": c["file_id"], "clip_name": c["name"]})
    if project and not segs:
        log("director", f"no approved segments for project '{project}', using all projects")
        return approved_segments(cfg, catalog, None, limit)
    segs.sort(key=lambda s: (-s.get("ad_score", 0), -s.get("usable_s", 0)))
    return segs[:limit or cfg["director"]["max_segments_in_prompt"]]


def assign_aliases(segs):
    """Long Drive ids get mistyped by the model; give every shot a short code (F01, T01) and map back in code."""
    f = t = 0
    for s in segs:
        if s.get("native_audio"):
            t += 1
            s["alias"] = f"T{t:02d}"
        else:
            f += 1
            s["alias"] = f"F{f:02d}"
    return {s["alias"]: s["segment_id"] for s in segs}


def resolve_aliases(plan, amap):
    """Turn short codes back into real segment ids (unknown codes are kept so the rule check reports them)."""
    def fix(x):
        return amap.get(str(x).strip().upper(), x)
    for s in plan.get("sentences", []):
        s["segment_ids"] = [fix(x) for x in (s.get("segment_ids") or [])]
        if s.get("native_segment_id"):
            s["native_segment_id"] = fix(s["native_segment_id"])
    for h in plan.get("hook_options", []):
        if h.get("segment_id"):
            h["segment_id"] = fix(h["segment_id"])
    for sh in plan.get("shot_list", []):
        if sh.get("segment_id"):
            sh["segment_id"] = fix(sh["segment_id"])
    return plan


def to_aliases(plan, amap):
    """Previous plan shown back to the director in short codes."""
    inv = {v: k for k, v in amap.items()}
    import copy
    p = copy.deepcopy(plan)
    for s in p.get("sentences", []):
        s["segment_ids"] = [inv.get(x, x) for x in (s.get("segment_ids") or [])]
        if s.get("native_segment_id"):
            s["native_segment_id"] = inv.get(s["native_segment_id"], s["native_segment_id"])
    for h in p.get("hook_options", []):
        h["segment_id"] = inv.get(h.get("segment_id"), h.get("segment_id"))
    return p


def segment_table(segs):
    lines = ["shot | shot_type | camera_move | score | usable_s | hero_at | description | tags"]
    for s in segs:
        if s.get("native_audio"):
            continue
        lines.append(f"{s['alias']} | {s['shot_type']} | {s['camera_move']} | {s['ad_score']} | "
                     f"{s['usable_s']} | {round(s['hero_second'] - s['in'], 1)} | {s['description']} | "
                     f"{', '.join(s.get('tags', []))}")
    return "\n".join(lines)


def native_table(segs):
    rows = [s for s in segs if s.get("native_audio")]
    if not rows:
        return "(none)"
    lines = ["shot | kind | score | seconds | what is seen | exact words (its own audio)"]
    for s in rows:
        lines.append(f"{s['alias']} | {s['kind']} | {s['ad_score']} | {s['usable_s']} | {s['description']} | \"{s['transcript']}\"")
    return "\n".join(lines)


def rubric_text():
    p = ROOT / "brand_voice_rubric.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ------------------------------------------------------------------ angles for a batch

def plan_angles(cfg, brief, n, style=None):
    """N distinct angles. Style angles first (proven), then Claude fills the rest."""
    style = style or {}
    base = [{"angle": a, "hook_idea": "", "emphasis": []} for a in style.get("angles", [])]
    if n <= len(base):
        return base[:n]
    content = f"""Brief:
{json.dumps(brief, indent=2, ensure_ascii=False)}

Angles already planned: {json.dumps([b['angle'] for b in base])}
Propose {n - len(base)} MORE clearly different creative angles for separate Meta lead-ad Reels from this brief.
Vary the hook type, the main benefit and the emotional tone. Stay within the brief's facts.
Return JSON: {{"angles": [{{"angle": "<name>", "hook_idea": "<one line>", "emphasis": ["<benefit>"]}}]}}"""
    data = ask_claude_json(cfg, "director_model", "You are a senior performance-ad strategist. Reply with JSON only.",
                           content, cache_system=False, temperature=1.0)
    extra = data.get("angles", [])
    out = base + extra
    while len(out) < n:
        out += out[: n - len(out)]
    return out[:n]


# ------------------------------------------------------------------ the plan

DIRECTOR_SYSTEM = """You are the creative director of a performance-marketing studio. You make 9:16 Reels that run as Meta lead ads for Indian real-estate brands, and you plan every video with a strict 10-step pre-production process before anything is produced.

You only use footage you are given (approved segments, already quality-checked) and only facts you are given. Every line's footage must visibly show what the line says.

Style pack for this video:
{style}

Brand rubric the plan will be judged against:
{rubric}

Reply with JSON only."""


def plan_video(cfg, brief, catalog, style, angle=None, feedback=None, previous=None, avoid_hooks=None):
    d = cfg["director"]
    segs = approved_segments(cfg, catalog, brief.get("project"))
    if not segs:
        raise RuntimeError("No approved segments in the catalog. Run analyze.py first.")
    amap = assign_aliases(segs)
    lo, hi = style.get("duration_seconds", [30, 40])
    wps = d["words_per_second"]
    system = DIRECTOR_SYSTEM.format(style=yaml.safe_dump(style, allow_unicode=True, sort_keys=False),
                                    rubric=rubric_text())
    parts = [f"""BRIEF (facts are the ONLY facts you may state)
{json.dumps(brief, indent=2, ensure_ascii=False)}

ANGLE FOR THIS VERSION
{json.dumps(angle or {}, ensure_ascii=False)}

APPROVED FOOTAGE ({len([s for s in segs if not s.get('native_audio')])} segments, best first; usable_s = seconds available; hero_at = seconds after segment start where its best moment is)
{segment_table(segs)}

CLIPS WITH THEIR OWN MEANINGFUL AUDIO (play as they are, never under the voiceover)
{native_table(segs)}

HARD RULES
1. Total spoken length {lo}-{hi} s: about {round(lo * wps)}-{round(hi * wps)} voiceover words at {wps} words/s (own-audio clips count their seconds).
2. Follow the style's beat order: {', '.join(b['beat'] for b in style['structure'])}. Tag every line with its beat.
3. Hook line: 12 words or fewer, over a high-score shot with motion. No logo, no price in the hook.
4. Every cut lasts at most {d['max_scene_seconds']} s. A line longer than that when spoken gets 2-3 segments, split evenly.
5. Each shot's usable_s >= its share of its line's spoken time. No shot used twice. Consecutive cuts never come from the same clip; vary framing and subject from cut to cut.
6. overlay = 2-5 word headline that adds meaning (not a copy of the line); "" when the shot should breathe. At most one overlay every other line.
7. Never use: {', '.join(cfg.get('banned_claims', []))}. No invented numbers, approvals, returns or appreciation promises.
8. Own-audio clips: at most {d['max_native_per_video']}; such a line is {{"native_segment_id": "<T code>", "text": "<its exact words>", "beat": "proof"}} with no segment_ids.
9. Write for the ear, conversational, as specified in the style's script_rules. Numbers spelled the way they are spoken.
10. If a needed shot does not exist, adapt the line; list the shot as missing in shot_list."""]
    if avoid_hooks:
        parts.append("Hooks already used in other versions (yours must be clearly different):\n- " + "\n- ".join(avoid_hooks))
    if previous and feedback:
        parts.append(f"YOUR PREVIOUS PLAN\n{json.dumps(to_aliases(previous, amap), ensure_ascii=False)}\n\n"
                     f"REVIEWER FEEDBACK (fix every point; keep what scored well)\n{json.dumps(feedback, ensure_ascii=False)}")
    parts.append("""Work through the 10 steps, then return ONE JSON object:
{
  "brief_check": {"format": "...", "platform": "...", "objective": "<one>", "audience": "...", "their_objection_we_answer": "..."},
  "references_applied": ["<which proven patterns from the style you used and how>"],
  "core_idea": "<the one thing people should remember, one sentence>",
  "angle": "<angle name>",
  "hook_options": [
    {"line": "<hook line>", "segment_id": "<shot code>", "why": "<why it stops the scroll>"},
    {"line": "...", "segment_id": "...", "why": "..."},
    {"line": "...", "segment_id": "...", "why": "..."}
  ],
  "sentences": [
    {"id": "s01", "beat": "hook", "text": "<spoken line; use hook option 1>", "segment_ids": ["<shot code>"],
     "visual": "<what the viewer sees>", "purpose": "<why this shot here>", "overlay": "<2-5 words or empty>",
     "transition": "cut", "caption_style": "hook"},
    {"id": "s02", "beat": "context", "text": "...", "segment_ids": ["..."], "visual": "...", "purpose": "...", "overlay": "", "transition": "cut", "caption_style": "normal"}
  ],
  "shot_list": [{"need": "<shot>", "status": "available | missing", "segment_id": "<shot code or empty>"}],
  "review": {"facts_used": ["<fact key from the brief>"], "risks": ["<anything a compliance reviewer might flag>"]},
  "post_caption": "<Instagram/Facebook post caption: 2-4 short lines, conversational, ends with the CTA>",
  "hashtags": ["<6-10 relevant hashtags>"],
  "video_title": "<short internal title>"
}
caption_style: "hook" for the first line, "cta" for the last, "normal" otherwise (own-audio lines are set automatically).
transition: "cut" (default) or "dissolve" (only for a deliberate mood change).""")
    parts.append("Refer to shots ONLY by their short code from the tables (e.g. F07, T01), exactly as written.")
    plan = ask_claude_json(cfg, "director_model", system, "\n\n".join(parts), temperature=cfg["director"].get("temperature", 0.9))
    plan = resolve_aliases(plan, amap)
    for i, s in enumerate(plan.get("sentences", []), 1):
        s["id"] = f"s{i:02d}"
        if isinstance(s.get("segment_ids"), str):
            s["segment_ids"] = [s["segment_ids"]]
        if s.get("native_segment_id"):
            s["segment_ids"] = [s["native_segment_id"]]
            s["caption_style"] = "native"
    plan["target_seconds"] = (lo + hi) / 2
    plan["duration_range"] = [lo, hi]
    plan["style"] = style.get("name")
    plan["project"] = brief.get("project")
    return plan


BATCH_SYSTEM = """You are the creative director of a performance-marketing studio making 9:16 Reels that run as Meta lead ads for Indian real-estate brands. You plan each video with a 10-step pre-production process (brief, objective, audience, references, core idea, script, storyboard, shot list, specs, review) and write compact, production-ready plans.

Use ONLY the footage and facts below. Every line's footage must visibly show what the line says.

STYLE PACK
{style}

BRAND RUBRIC
{rubric}

BRIEF (the only facts you may state)
{brief}

APPROVED FOOTAGE (shot code | shot_type | camera_move | score | usable_s | hero_at | description | tags)
{footage}

CLIPS WITH THEIR OWN MEANINGFUL AUDIO (play as they are, never under the voiceover)
{native}

HARD RULES
1. Spoken length {lo}-{hi} s: about {wlo}-{whi} voiceover words at {wps} words/s (own-audio clips count their seconds).
2. Beat order: {beats}. Tag every line with its beat.
3. Hook: 12 words or fewer, over a high-score shot with motion; no logo, no price.
4. Each cut <= {max_scene} s; a line longer than that gets 2-3 shots, split evenly. Each shot's usable_s >= its share.
5. No shot used twice in a video; consecutive cuts never from the same clip; vary subject and framing.
6. overlay: 2-5 word sentence-case headline adding meaning, or "" (at most every other line).
7. Never: {banned}. No invented numbers, approvals, returns or appreciation promises.
8. Own-audio clips: at most {max_native}; such a line is {{"native_segment_id": "<T code>", "text": "<exact words>", "beat": "proof"}}.
9. Conversational, for the ear (contractions, short sentences). Numbers spelled as spoken.
10. Refer to shots ONLY by their short code (F07, T01) exactly as written.

Reply with JSON only."""


def batch_system(cfg, brief, style, segs):
    d = cfg["director"]
    lo, hi = style.get("duration_seconds", [30, 40])
    wps = d["words_per_second"]
    return BATCH_SYSTEM.format(
        style=yaml.safe_dump({k: style[k] for k in style if k not in ("name",)}, allow_unicode=True, sort_keys=False),
        rubric=rubric_text(), brief=json.dumps(brief, indent=1, ensure_ascii=False),
        footage="\n".join(segment_table(segs).splitlines()[1:]), native=native_table(segs),
        lo=lo, hi=hi, wlo=round(lo * wps), whi=round(hi * wps), wps=wps, beats=", ".join(b["beat"] for b in style["structure"]),
        max_scene=d["max_scene_seconds"], banned=", ".join(cfg.get("banned_claims", [])),
        max_native=d["max_native_per_video"])


def generate_candidates(cfg, brief, catalog, style, angle=None, n=None, avoid_hooks=None, feedback=None):
    """ONE Claude call -> n complete video plans (different hooks/approaches within the angle).
    The system prompt (style, rubric, brief, footage) is identical across a batch, so it is cached."""
    n = n or cfg["director"].get("candidates_per_call", 5)
    segs = approved_segments(cfg, catalog, brief.get("project"))
    if not segs:
        raise RuntimeError("No approved segments in the catalog. Run analyze.py first.")
    amap = assign_aliases(segs)
    lo, hi = style.get("duration_seconds", [30, 40])
    ask = [f"ANGLE: {json.dumps(angle or {}, ensure_ascii=False)}",
           f"Write {n} clearly different versions for this angle (different hooks, different shot choices, "
           f"same core facts). Each must stand alone as a finished plan."]
    if avoid_hooks:
        ask.append("Hooks already used in other videos (do not reuse):\n- " + "\n- ".join(avoid_hooks))
    if feedback:
        ask.append("Last round's problems to avoid:\n- " + "\n- ".join(feedback[:8]))
    ask.append("""Return JSON:
{"versions": [
  {"core_idea": "<one sentence>", "video_title": "<short>",
   "sentences": [
     {"beat": "hook", "text": "<spoken line>", "segment_ids": ["F07"], "overlay": "<2-5 words or empty>", "caption_style": "hook"},
     {"beat": "context", "text": "...", "segment_ids": ["F12", "F03"], "overlay": "", "caption_style": "normal"}
   ],
   "missing_shots": ["<shot the idea needed but the footage lacks>"],
   "post_caption": "<2-4 short conversational lines ending with the CTA>",
   "hashtags": ["<6-10>"]}
]}
The last line has beat "cta" and caption_style "cta". Keep it compact: no extra fields.""")
    data = ask_claude_json(cfg, "director_model", batch_system(cfg, brief, style, segs), "\n\n".join(ask))
    out = []
    for v in data.get("versions", [])[:n]:
        v = resolve_aliases(v, amap)
        for i, s in enumerate(v.get("sentences", []), 1):
            s["id"] = f"s{i:02d}"
            if isinstance(s.get("segment_ids"), str):
                s["segment_ids"] = [s["segment_ids"]]
            if s.get("native_segment_id"):
                s["segment_ids"] = [s["native_segment_id"]]
                s["caption_style"] = "native"
        v.update(angle=(angle or {}).get("angle"), target_seconds=(lo + hi) / 2, duration_range=[lo, hi],
                 style=style.get("name"), project=brief.get("project"))
        out.append(v)
    return out, segs


def apply_hook(plan, index):
    """Swap the first line for another hook option (the judge may prefer a different one)."""
    opts = plan.get("hook_options") or []
    if not (0 <= index < len(opts)) or not plan.get("sentences"):
        return plan
    h, s1 = opts[index], plan["sentences"][0]
    s1["text"] = h["line"]
    if h.get("segment_id"):
        s1["segment_ids"] = [h["segment_id"]]
    plan["chosen_hook"] = index
    return plan


# back-compat name used by older callers
def write_script(cfg, brief, catalog, angle=None, feedback=None, previous=None, avoid_hooks=None, style=None):
    return plan_video(cfg, brief, catalog, style or load_style(cfg["director"].get("default_style", "weekend_home")),
                      angle, feedback, previous, avoid_hooks)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="brief.json")
    ap.add_argument("--style", default="weekend_home")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    plan = plan_video(cfg, read_json(a.brief), read_json(cfg["_paths"]["catalog_file"], {"clips": {}}), load_style(a.style))
    write_json(Path(a.run_dir) / "plan.json", plan)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
