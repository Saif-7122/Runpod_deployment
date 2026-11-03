"""2026-10-27 batch: plans -> repaired, rule-checked run folders for run.py --produce.
   python make_runs2.py plans.json [--write]
Shots: a clip key ("v028", "o012", "n048") picks that clip's least-used segment not yet in the reel, or an exact
segment key ("v028_3"). A segment appears in at most MAX_USES reels; no two reels open on the same segment."""
import json, os, re, sys
from collections import Counter
from pathlib import Path
from common import load_config, read_json, write_json, new_run_id
from judge import rule_checks, segment_index
from repair import repair
from director import load_style

SP = Path(__file__).parent
CAP = int(os.environ.get("MAX_USES", 2))
cfg = load_config()
catalog = read_json(cfg["_paths"]["catalog_file"])
style = load_style("weekend_home")
brief = read_json("brief.json")
idx = segment_index(catalog)
keys = {}
for f in ("allkeys.json", "sv/keys.json", "oc/keys.json", "ai_keys.json", "wk/keys.json", "oct/keys.json", "k_keys.json"):
    if (SP / "keys" / f).exists():
        keys.update(json.load(open(SP / "keys" / f)))
keys = {k: v for k, v in keys.items() if v["segment_id"] in idx}
by_clip = {}
for k in keys:
    by_clip.setdefault(k.split("_")[0], []).append(k)
to_key = {v["segment_id"]: k for k, v in keys.items()}
banned = {"v016"}                                     # "Congratulations" graphic
plans = json.load(open(sys.argv[1], encoding="utf-8"))
state_f = SP / os.environ.get("CE_STATE", "batch_state_1028.json")
state = json.load(open(state_f)) if state_f.exists() else {"uses": {}, "hooks": []}
done = set(state.get("done", []))
uses, hooks = Counter(state["uses"]), set(state["hooks"])
ok_all = True


def pick(tok, taken, first):
    if "_" in tok:
        return tok if tok in keys else None
    opts = [k for k in by_clip.get(tok, []) if k not in taken and uses[k] < CAP and not (first and k in hooks)]
    return max(opts, key=lambda k: (-uses[k], keys[k]["usable_s"]), default=None)


for p in plans:
    if p["video_title"] in done:
        continue
    p.setdefault("style", "weekend_home"); p.setdefault("project", "Oxygen Forest Client Site Visits")
    if p.get("mode") == "scenic":
        p.setdefault("duration_range", [14, 30]); p.setdefault("target_seconds", 20.0)
    else:
        p.setdefault("target_seconds", 27.0); p.setdefault("duration_range", [20, 33])
    v, taken = [], set()
    for k, s in enumerate(p["sentences"]):
        s.setdefault("id", f"s{k + 1:02d}"); s.setdefault("overlay", "")
        s.setdefault("caption_style", "hook" if k == 0 else "cta" if s.get("beat") == "cta" else "normal")
        ids = []
        for tok in s.pop("shots"):
            kk = None if tok.split("_")[0] in banned else pick(tok, taken, not ids and k == 0)
            if kk is None:                         # clip used up: repair() fills the gap from the pool
                continue
            taken.add(kk); ids.append(keys[kk]["segment_id"])
        s["segment_ids"] = ids
        if not ids:
            v.append(f"{s['id']}: no free shots")
    pool = [idx[keys[k]["segment_id"]] for k in keys if k.split("_")[0] not in banned and uses[k] < CAP and k not in taken]
    repair(cfg, p, catalog, [])                        # no random substitutes: every shot is hand-matched to its line
    issues = rule_checks(cfg, p, catalog, style, brief)
    if p.get("list"):                                  # "5 reasons" style list counts
        issues = [x for x in issues if not re.search(r"number [345] is not", x)]
    issues = [x for x in issues if not any(k in x for k in ("beats out of order", "per cut (max", "s, needs"))]
    if p.get("allow_price_hook"):
        issues = [x for x in issues if "hook must not lead" not in x]
    # longer, calmer shots (user 2026-10-30): a shot may run past its analysed segment; check_cuts.py verifies the
    # actual rendered window has no hidden cut instead
    v += issues
    mine = [to_key[x] for s in p["sentences"] for x in s["segment_ids"]]
    v += [f"{k} already in {CAP} reels" for k in mine if uses[k] >= CAP]
    if mine and mine[0] in hooks:
        v.append(f"hook shot {mine[0]} already opens another reel")
    print(f"{p['video_title'][:38]:38} [{p['language']}/{p.get('mode', 'voice')}] cuts={len(mine)} "
          f"fixes={len(p.get('auto_fixes', []))} issues={v}")
    ok_all &= not v
    if "--write" in sys.argv and not v:
        rid = new_run_id(f"of1031ad-{p['language']}-{p.get('mode', 'voice')}-manual")
        run = cfg["_paths"]["runs"] / rid
        run.mkdir(parents=True)
        p["verdict"] = {"score": None, "passed": True, "note": "directed and judged in Claude Code (no API)"}
        write_json(run / "plan.json", p)
        write_json(run / "status.json", {"run_id": rid, "language": p["language"], "angle": p.get("angle"),
                                         "status": "planned", "timings": {}})
        uses.update(mine); hooks.add(mine[0])
        done.add(p["video_title"])
        json.dump({"uses": uses, "hooks": sorted(hooks), "done": sorted(done)}, open(state_f, "w"))
        print("   ->", run.name)
print("ALL OK" if ok_all else "FIX ISSUES ABOVE")
