"""Make videos end to end: director -> judge (max 3 rewrites) -> TTS -> fit timeline -> render -> upload.

  python run.py --brief brief.json                         # one video
  python run.py --brief brief.json --variants 50 --parallel 8 --upload
  python run.py --brief brief.json --mock-tts --no-upload  # local test without Sarvam

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

from common import load_config, log, new_run_id, read_json, write_json
from director import plan_angles, write_script
from fit_timeline import fit
from judge import judge
from render import render
from tts import synthesize


class Batch:
    def __init__(self, cfg, args):
        self.cfg, self.args = cfg, args
        self.catalog = read_json(cfg["_paths"]["catalog_file"], {"clips": {}})
        self.render_slots = threading.Semaphore(cfg["rendering"].get("parallel_renders", 4))
        self.hooks, self.lock = [], threading.Lock()
        self.out_folder = None

    def upload_folder(self):
        with self.lock:
            if self.out_folder is None:
                import drive
                root = self.cfg["drive"]["output_folder_id"]
                self.out_folder = drive.ensure_folder(root, datetime.now().strftime("%Y-%m-%d"))
            return self.out_folder

    def make_video(self, brief, angle, n):
        cfg, a = self.cfg, self.args
        run_id = new_run_id(f"{brief.get('project', 'ad')}-{n:02d}")
        run = cfg["_paths"]["runs"] / run_id
        run.mkdir(parents=True)
        status = {"run_id": run_id, "variant": n, "angle": angle.get("angle"), "status": "started", "timings": {}}
        write_json(run / "brief.json", brief)

        def step(name, fn):
            t0 = time.time()
            res = fn()
            status["timings"][name] = round(time.time() - t0, 1)
            write_json(run / "status.json", status)
            return res

        try:
            attempts, script, verdict = [], None, None
            for attempt in range(1, cfg["judge"]["max_attempts"] + 1):
                with self.lock:
                    avoid = list(self.hooks)
                script = step(f"director_{attempt}", lambda: write_script(
                    cfg, brief, self.catalog, angle,
                    feedback=verdict["feedback"] if verdict else None, previous=script, avoid_hooks=avoid))
                verdict = step(f"judge_{attempt}", lambda: judge(cfg, brief, script, self.catalog))
                attempts.append({"attempt": attempt, "script": script, "verdict": verdict})
                write_json(run / "judge.json", attempts)
                if verdict["passed"]:
                    break
            write_json(run / "script.json", script)
            status["score"] = verdict["score"]
            if not verdict["passed"]:
                status["status"] = "needs_human"
                status["feedback"] = verdict["feedback"]
                write_json(run / "status.json", status)
                log("run", f"{run_id}: failed judge after {len(attempts)} attempts -> needs_human")
                return status
            with self.lock:
                self.hooks.append(script["sentences"][0]["text"])

            audio = step("tts", lambda: synthesize(cfg, script, run, mock=a.mock_tts, catalog=self.catalog))
            step("fit", lambda: fit(cfg, script, audio, self.catalog, run))
            with self.render_slots:
                out, _ = step("render", lambda: render(cfg, run))
            status["video"] = str(out)
            if a.upload:
                import drive
                folder = self.upload_folder()
                name = f"{run_id}.mp4"
                f = step("upload", lambda: drive.upload(out, folder, name))
                drive.upload(run / "edit_project_source.json", folder, f"{run_id}_project.json", "application/json")
                status["drive_link"] = f.get("webViewLink")
            status["status"] = "done"
            if a.cleanup and a.upload:
                for p in (run / "audio").glob("*.wav"):
                    p.unlink()
            log("run", f"{run_id}: done (score {verdict['score']}, {sum(status['timings'].values()):.0f} s)")
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
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.upload is None:
        args.upload = bool(cfg["drive"].get("upload_by_default"))

    batch = Batch(cfg, args)
    if not batch.catalog["clips"]:
        raise SystemExit("Catalog is empty. Run: python analyze.py --drive")
    jobs = []
    for bpath in args.brief:
        brief = read_json(bpath)
        angles = plan_angles(cfg, brief, args.variants)
        log("run", f"{bpath}: {len(angles)} angles planned")
        jobs += [(brief, ang, i + 1) for i, ang in enumerate(angles)]

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.parallel or cfg["batch"]["parallel_videos"]) as pool:
        futs = [pool.submit(batch.make_video, b, ang, n) for b, ang, n in jobs]
        for f in as_completed(futs):
            results.append(f.result())
    wall = time.time() - t0
    done = [r for r in results if r["status"] == "done"]
    report = {
        "finished_at": datetime.now().isoformat(timespec="seconds"), "wall_seconds": round(wall, 1),
        "videos_done": len(done), "videos_total": len(results),
        "videos_per_hour": round(len(done) / wall * 3600, 1) if wall else 0,
        "results": sorted(results, key=lambda r: r["run_id"]),
    }
    rp = cfg["_paths"]["runs"] / f"batch-{datetime.now():%Y%m%d-%H%M%S}.json"
    write_json(rp, report)
    log("run", f"{len(done)}/{len(results)} videos in {wall / 60:.1f} min "
               f"({report['videos_per_hour']} per hour). Report: {rp}")
    print(json.dumps({k: report[k] for k in ("videos_done", "videos_total", "wall_seconds", "videos_per_hour")}))


if __name__ == "__main__":
    main()
