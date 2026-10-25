"""Make videos end to end (cost-optimised):
   1 Sonnet call -> 5 candidate plans -> free auto-repair + rule checks -> 1 Haiku call ranks them
   -> top 2: voice (local GPU) + quick draft render -> video judge (local, threshold)
   -> best passing draft: final render -> post caption -> upload.   Claude spend is capped per batch.

  python run.py --brief brief.json --variants 3 --upload           # 3 reels, different angles
  python run.py --brief brief.json --variants 3 --plan-only         # plans + gate only (no voice/render cost)
  python run.py --produce workspace/runs/<run_id> ... --upload      # produce plans that already passed the gate
  python run.py --brief brief.json --mock-tts --no-upload           # local test without Sarvam

Writes each video to workspace/runs/<run_id>/ and a batch report to workspace/runs/batch-<time>.json.
"""
import argparse
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from common import BudgetExceeded, load_config, log, new_run_id, read_json, usage_cost, usage_snapshot, write_json
from director import generate_candidates, load_style, plan_angles
from fit_timeline import fit
from judge import rank_candidates, rule_checks
from repair import repair
from video_judge import judge_video
from render import render
from tts import synthesize


class Batch:
    def __init__(self, cfg, args):
        self.cfg, self.args = cfg, args
        self.catalog = read_json(cfg["_paths"]["catalog_file"], {"clips": {}})
        self.render_slots = threading.Semaphore(cfg["rendering"].get("parallel_renders", 4))
        self.hooks, self.lock = [], threading.Lock()
        self.out_folder = None
        self.style = load_style(args.style or cfg["director"].get("default_style", "weekend_home"))

    def upload_folder(self):
        with self.lock:
            if self.out_folder is None:
                import drive
                root = self.cfg["drive"]["output_folder_id"]
                self.out_folder = drive.ensure_folder(root, datetime.now().strftime("%Y-%m-%d"))
            return self.out_folder

    def make_video(self, brief, angle, n):
        cfg, a = self.cfg, self.args
        style = self.style
        run_id = new_run_id(f"{style['name']}-{n:02d}")
        run = cfg["_paths"]["runs"] / run_id
        run.mkdir(parents=True)
        status = {"run_id": run_id, "variant": n, "style": style["name"], "angle": angle.get("angle"),
                  "status": "started", "timings": {}}
        write_json(run / "brief.json", brief)

        def step(name, fn):
            t0 = time.time()
            res = fn()
            status["timings"][name] = round(time.time() - t0, 1)
            write_json(run / "status.json", status)
            return res

        try:
            jc = cfg["judge"]
            passed, feedback, cands = [], None, []
            for attempt in range(1, jc["max_attempts"] + 1):
                with self.lock:
                    avoid = list(self.hooks)
                (cands, segs) = step(f"director_{attempt}", lambda: generate_candidates(
                    cfg, brief, self.catalog, style, angle, avoid_hooks=avoid, feedback=feedback))
                ok = []
                for k, c in enumerate(cands):
                    repair(cfg, c, self.catalog, segs)               # free fixes before any paid review
                    c["rule_violations"] = rule_checks(cfg, c, self.catalog, style)
                    if not c["rule_violations"]:
                        ok.append(c)
                log("run", f"{run_id}: attempt {attempt}: {len(ok)}/{len(cands)} candidates pass the rules")
                if ok:
                    ranked = step(f"judge_{attempt}", lambda: rank_candidates(cfg, brief, ok, self.catalog, style))
                    passed = [c for c in ranked if c["verdict"]["passed"]]
                    write_json(run / "candidates.json", {"attempt": attempt, "ranked": ranked,
                                                          "rejected_by_rules": [c for c in cands if c["rule_violations"]]})
                    log("run", f"{run_id}: judge -> {len(passed)} pass; best "
                               f"{ranked[0]['verdict']['score']} {ranked[0]['verdict']['scores']}")
                    if passed:
                        break
                    feedback = [f for c in ranked[:2] for f in c["verdict"]["gate_fails"] + c["verdict"]["fixes"]]
                else:
                    feedback = [v for c in cands for v in c["rule_violations"]][:8]
            status["claude_usd_so_far"] = usage_cost(cfg)
            if not passed:
                status.update(status="needs_human", feedback=feedback)
                write_json(run / "status.json", status)
                log("run", f"{run_id}: no candidate passed the script gate -> needs_human")
                return status
            with self.lock:
                self.hooks.append(passed[0]["sentences"][0]["text"])
            top = passed[: cfg["video_judge"].get("drafts", 2)]
            for i, c in enumerate(top):
                write_json(run / f"plan_{i + 1}.json", c)
            status.update(status="planned", score=top[0]["verdict"]["score"])
            if a.plan_only:
                write_json(run / "plan.json", top[0])
                write_json(run / "status.json", status)
                log("run", f"{run_id}: plan-only: best script {top[0]['verdict']['score']}, not produced")
                return status
            # drafts: voice + quick render + video judge; keep the best passing draft
            best = None
            for i, c in enumerate(top):
                d = run / f"draft_{i + 1}"
                d.mkdir(exist_ok=True)
                audio = step(f"tts_draft{i + 1}", lambda: synthesize(cfg, c, d, mock=a.mock_tts, catalog=self.catalog))
                step(f"fit_draft{i + 1}", lambda: fit(cfg, c, audio, self.catalog, d))
                with self.render_slots:
                    dv, _ = step(f"render_draft{i + 1}", lambda: render(cfg, d, draft=True))
                vj = step(f"video_judge{i + 1}", lambda: judge_video(cfg, d, dv))
                c["video_verdict"] = vj
                log("run", f"{run_id}: draft {i + 1} video score {vj['score']} {'PASS' if vj['passed'] else vj['fails']}")
                if vj["passed"] and (best is None or vj["score"] > best[1]["video_verdict"]["score"]):
                    best = (d, c)
            if best is None:
                status.update(status="needs_human", feedback=[f for c in top for f in c["video_verdict"]["fails"]])
                write_json(run / "status.json", status)
                log("run", f"{run_id}: no draft passed the video judge -> needs_human")
                return status
            d, c = best
            write_json(run / "plan.json", c)
            write_json(d / "plan.json", c)
            return self.produce(d, status, c, c["verdict"]["score"], step, reuse_audio=True)
        except BudgetExceeded as e:
            status.update(status="stopped_budget", error=str(e))
            log("run", f"{run_id}: {e}")
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"{e}"
            (run / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            log("run", f"{run_id}: ERROR {e}")
        write_json(run / "status.json", status)
        return status

    def produce(self, run, status, script, score, step=None, reuse_audio=False):
        """Voice -> timeline -> render -> post caption -> upload, for a plan that passed the gate."""
        cfg, a = self.cfg, self.args
        run_id = status.get("run_id", run.name)
        if step is None:
            def step(name, fn):
                t0 = time.time()
                res = fn()
                status["timings"][name] = round(time.time() - t0, 1)
                write_json(run / "status.json", status)
                return res
        try:

            if not reuse_audio:
                audio = step("tts", lambda: synthesize(cfg, script, run, mock=a.mock_tts, catalog=self.catalog))
                step("fit", lambda: fit(cfg, script, audio, self.catalog, run))
            with self.render_slots:
                out, _ = step("render", lambda: render(cfg, run))
            status["video"] = str(out)
            # post caption for Instagram / Facebook (the text that goes under the Reel)
            cap = (script.get("post_caption", "").strip() + "\n\n" + " ".join(
                h if h.startswith("#") else "#" + h for h in script.get("hashtags", []))).strip()
            (run / "post_caption.txt").write_text(cap + "\n", encoding="utf-8")
            # post-render QA: spec checks that cost nothing
            tl = read_json(run / "timeline.json")
            lo, hi = script.get("duration_range", [30, 40])
            dur = tl["total_duration_seconds"]
            status["duration_seconds"] = dur
            if not (lo - 1 <= dur <= hi + cfg["rendering"].get("tail_seconds", 1.5) + 1):
                status["qa_warning"] = f"duration {dur:.1f} s outside {lo}-{hi} s"
            if a.upload:
                import drive
                folder = self.upload_folder()
                title = script.get("video_title") or run_id
                name = f"{run_id} - {title}"
                f = step("upload", lambda: drive.upload(out, folder, name + ".mp4"))
                drive.upload(run / "post_caption.txt", folder, name + " - caption.txt", "text/plain")
                drive.upload(run / "edit_project_source.json", folder, name + " - project.json", "application/json")
                status["drive_link"] = f.get("webViewLink")
            status["status"] = "done"
            status.pop("error", None)                  # clear a failure left by an earlier attempt
            if a.cleanup and a.upload:
                for p in (run / "audio").glob("*.wav"):
                    p.unlink()
            log("run", f"{run_id}: done (score {score}, {status.get('duration_seconds', 0):.1f} s video, "
                       f"{sum(status['timings'].values()):.0f} s work)")
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"{e}"
            (run / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            log("run", f"{run_id}: ERROR {e}")
        write_json(run / "status.json", status)
        return status


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", nargs="+", default=["brief.json"], help="one or more brief files")
    ap.add_argument("--variants", type=int, default=1, help="videos per brief, each with a different angle")
    ap.add_argument("--parallel", type=int, default=0, help="videos in flight at once")
    ap.add_argument("--upload", dest="upload", action="store_true", default=None)
    ap.add_argument("--no-upload", dest="upload", action="store_false")
    ap.add_argument("--mock-tts", action="store_true", help="skip Sarvam; quiet placeholder audio")
    ap.add_argument("--cleanup", action="store_true", help="delete per-sentence WAVs after upload")
    ap.add_argument("--style", help="style pack in styles/ (default: director.default_style)")
    ap.add_argument("--plan-only", action="store_true", help="plan + gate only; no voice, render or upload")
    ap.add_argument("--produce", nargs="+", help="run folders whose plan already passed: voice + render + upload")
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.upload is None:
        args.upload = bool(cfg["drive"].get("upload_by_default"))

    batch = Batch(cfg, args)
    if not batch.catalog["clips"]:
        raise SystemExit("Catalog is empty. Run: python analyze.py --drive")
    if args.produce:
        results = []
        for rd in args.produce:
            run = Path(rd)
            st = read_json(run / "status.json", {"run_id": run.name, "timings": {}})
            st.setdefault("timings", {})
            plan = read_json(run / "plan.json")
            score = st.get("score", 0)
            results.append(batch.produce(run, st, plan, score))
        print(json.dumps([{k: r.get(k) for k in ("run_id", "status", "duration_seconds", "drive_link", "error")} for r in results], indent=2))
        return
    jobs = []
    for bpath in args.brief:
        brief = read_json(bpath)
        angles = plan_angles(cfg, brief, args.variants, batch.style)
        log("run", f"{bpath}: {len(angles)} angles planned")
        jobs += [(brief, ang, i + 1) for i, ang in enumerate(angles)]

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.parallel or cfg["batch"]["parallel_videos"]) as pool:
        futs = [pool.submit(batch.make_video, b, ang, n) for b, ang, n in jobs]
        for f in as_completed(futs):
            results.append(f.result())
    wall = time.time() - t0
    done = [r for r in results if r["status"] in ("done", "planned")]
    report = {
        "claude_usage": usage_snapshot(),
        "claude_usd": usage_cost(cfg),
        "finished_at": datetime.now().isoformat(timespec="seconds"), "wall_seconds": round(wall, 1),
        "videos_done": len(done), "videos_total": len(results),
        "videos_per_hour": round(len(done) / wall * 3600, 1) if wall else 0,
        "results": sorted(results, key=lambda r: r["run_id"]),
    }
    rp = cfg["_paths"]["runs"] / f"batch-{datetime.now():%Y%m%d-%H%M%S}.json"
    write_json(rp, report)
    log("run", f"Claude spend this batch: ${usage_cost(cfg):.3f}")
    log("run", f"{len(done)}/{len(results)} videos in {wall / 60:.1f} min "
               f"({report['videos_per_hour']} per hour). Report: {rp}")
    print(json.dumps({k: report[k] for k in ("videos_done", "videos_total", "wall_seconds", "videos_per_hour")}))


if __name__ == "__main__":
    main()
