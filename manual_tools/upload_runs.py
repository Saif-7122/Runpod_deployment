"""Upload rendered manual runs (video + post caption + project file) to drive.output_folder_id, like run.py --upload."""
import sys
from pathlib import Path
import drive
from common import load_config, read_json, write_json

cfg = load_config()
folder = cfg["drive"]["output_folder_id"]
if len(sys.argv) > 2:                         # e.g. a dated subfolder: upload_runs.py "<glob>" 2026-10-27
    folder = drive.ensure_folder(folder, sys.argv[2])
for run in sorted(cfg["_paths"]["runs"].glob(sys.argv[1] if len(sys.argv) > 1 else "*-manual-*")):
    st = read_json(run / "status.json", {})
    out = run / "finished_ad.mp4"
    if st.get("drive_link") or not out.exists() or st.get("status") != "done":
        continue
    plan = read_json(run / "plan.json")
    name = f"{plan['language'].upper()} - {plan['video_title']} - {run.name[-4:]}"
    f = drive.upload(out, folder, name + ".mp4")
    drive.upload(run / "post_caption.txt", folder, name + " - caption.txt", "text/plain")
    drive.upload(run / "edit_project_source.json", folder, name + " - project.json", "application/json")
    st["drive_link"] = f.get("webViewLink")
    write_json(run / "status.json", st)
    print(name, st["drive_link"], flush=True)
