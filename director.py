"""Director: Claude writes script.json from the brief + approved segments (no times).

  python director.py --brief brief.json --run-dir workspace/runs/test   # one script
"""
import argparse
import json
from pathlib import Path

from common import ROOT, ask_claude_json, load_config, log, read_json, write_json


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


def segment_table(segs):
    lines = ["segment_id | shot_type | camera_move | score | usable_s | hero_at | description | tags"]
    for s in segs:
        if s.get("native_audio"):
            continue
        lines.append(f"{s['segment_id']} | {s['shot_type']} | {s['camera_move']} | {s['ad_score']} | "
                     f"{s['usable_s']} | {round(s['hero_second'] - s['in'], 1)} | {s['description']} | "
                     f"{', '.join(s.get('tags', []))}")
    return "\n".join(lines)


def native_table(segs):
    rows = [s for s in segs if s.get("native_audio")]
    if not rows:
        return "(none)"
    lines = ["segment_id | kind | score | seconds | what is seen | exact words (its own audio)"]
    for s in rows:
        lines.append(f"{s['segment_id']} | {s['kind']} | {s['ad_score']} | {s['usable_s']} | {s['description']} | \"{s['transcript']}\"")
    return "\n".join(lines)


def rubric_text():
    p = ROOT / "brand_voice_rubric.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


DIRECTOR_SYSTEM = """You are the creative director of a performance-marketing studio that makes high-retention 9:16 real-estate ads for Indian buyers (Instagram Reels, YouTube Shorts).
You write the voiceover AND choose the footage for every line, using ONLY the approved footage segments you are given.
Every line must be shown by a segment whose description actually matches it. Never describe something no segment shows.

Brand rubric the work is judged against:
{rubric}

Reply with JSON only."""


def plan_angles(cfg, brief, n):
    """N distinct creative angles (hook + emphasis) so batch variants don't look the same."""
    if n <= 1:
        return [{"angle": brief.get("hook_angle", ""), "hook_idea": brief.get("hook_angle", ""), "emphasis": []}]
    content = f"""Brief:
{json.dumps(brief, indent=2, ensure_ascii=False)}

Propose {n} clearly different creative angles for separate ads from this brief.
Vary the hook type (question, bold claim, pain point, curiosity, number, POV, comparison), the main benefit emphasised and the emotional tone.
Stay within the brief's facts. Return JSON: {{"angles": [{{"angle": "<name>", "hook_idea": "<one line>", "emphasis": ["<benefit>", "..."]}}]}}"""
    data = ask_claude_json(cfg, "director_model", "You are a senior ad strategist. Reply with JSON only.",
                           content, max_tokens=4000, cache_system=False)
    angles = data.get("angles", [])
    while len(angles) < n:
        angles += angles[: n - len(angles)] or [{"angle": "default", "hook_idea": "", "emphasis": []}]
    return angles[:n]


def write_script(cfg, brief, catalog, angle=None, feedback=None, previous=None, avoid_hooks=None):
    d = cfg["director"]
    segs = approved_segments(cfg, catalog, brief.get("project"))
    if not segs:
        raise RuntimeError("No approved segments in the catalog. Run analyze.py first.")
    target = float(brief.get("target_duration_seconds", d["default_target_seconds"]))
    wps = d["words_per_second"]
    system = DIRECTOR_SYSTEM.format(rubric=rubric_text())

    parts = [f"""BRIEF
{json.dumps(brief, indent=2, ensure_ascii=False)}

CREATIVE ANGLE FOR THIS VERSION
{json.dumps(angle or {}, ensure_ascii=False)}

APPROVED FOOTAGE ({len(segs)} segments, best first; usable_s = seconds available; hero_at = seconds after segment start where its best moment is)
{segment_table(segs)}

CLIPS WITH THEIR OWN MEANINGFUL AUDIO (testimonials, presenters, edited pieces). Play them as they are, never under the voiceover:
{native_table(segs)}

RULES
1. Total voiceover about {round(target * wps)} words ({target:.0f} s at {wps} words/s).
2. Sentence 1 is the hook: 12 words or fewer, and its first segment is a high-score shot with a strong hero moment.
3. Every cut lasts at most {d['max_scene_seconds']} s. A sentence longer than {d['max_scene_seconds']} s when spoken ({wps} words/s) gets 2 segments (or 3), split evenly across them.
4. Each segment's usable_s must be at least its share of its sentence's spoken time.
5. Each segment's description must show what its sentence says. No segment used twice. Two consecutive segments never share both shot_type and camera_move, and never come from the same clip.
6. Flow: wide/establishing -> details -> lifestyle/amenities -> location/access -> CTA over a strong hero shot.
7. overlay: 2-6 punchy words per sentence that reinforce (not repeat) the line; empty string allowed.
8. The last sentence is the call to action with caption_style "cta"; sentence 1 has caption_style "hook"; others "normal".
9. Never use these claims: {', '.join(cfg.get('banned_claims', []))}. No invented prices, approvals or numbers not in the brief.
10. If the brief mentions something no segment shows, leave it out and list it in missing_shots.
11. Write for the ear: short, rhythmic, plain Indian English.
12. Own-audio clips: use at most {d['max_native_per_video']} where they add proof or emotion (a testimonial after the claims is ideal).
    Such a line is {{"native_segment_id": "<id>", "text": "<its exact words>", "overlay": "...", "caption_style": "native"}} and has no segment_ids.
    Its seconds count toward the total length; write fewer voiceover words to compensate (total spoken time ~{target:.0f} s)."""]
    if avoid_hooks:
        parts.append("Hooks already used in other versions (write a different one):\n- " + "\n- ".join(avoid_hooks))
    if previous and feedback:
        parts.append(f"YOUR PREVIOUS DRAFT\n{json.dumps(previous, ensure_ascii=False)}\n\n"
                     f"JUDGE FEEDBACK (fix every point)\n{json.dumps(feedback, ensure_ascii=False)}")
    parts.append("""Return JSON:
{
  "video_title": "<short title>",
  "angle": "<angle name>",
  "sentences": [
    {"id": "s01", "text": "<spoken line>", "segment_ids": ["<segment_id>"], "overlay": "<2-6 words>", "caption_style": "hook"}
  ],
  "missing_shots": ["<shot the brief needed but the footage lacks>"]
}""")
    script = ask_claude_json(cfg, "director_model", system, "\n\n".join(parts), max_tokens=4000)
    for i, s in enumerate(script.get("sentences", []), 1):
        s["id"] = f"s{i:02d}"
        if isinstance(s.get("segment_ids"), str):
            s["segment_ids"] = [s["segment_ids"]]
        if s.get("native_segment_id"):
            s["segment_ids"] = [s["native_segment_id"]]
            s["caption_style"] = "native"
    script["target_seconds"] = target
    script["project"] = brief.get("project")
    return script


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="brief.json")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = load_config(a.config)
    sc = write_script(cfg, read_json(a.brief), read_json(cfg["_paths"]["catalog_file"], {"clips": {}}))
    write_json(Path(a.run_dir) / "script.json", sc)
    print(json.dumps(sc, indent=2, ensure_ascii=False))
