import os
import sys
import json
import argparse
import yaml

def load_yaml(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def fit_timeline(run_dir, config_path="config.yaml"):
    config = load_yaml(config_path)
    dirs = config.get("directories", {})
    catalog_path = os.path.join(dirs.get("catalog", "/workspace/catalog"), "catalog.json")

    timeline_path = os.path.join(run_dir, "timeline.json")
    audio_meta_path = os.path.join(run_dir, "audio_meta.json")
    output_timeline_path = os.path.join(run_dir, "fitted_timeline.json")
    download_queue_path = os.path.join(run_dir, "download_queue.json")

    if not os.path.exists(timeline_path):
        raise FileNotFoundError(f"Timeline not found at {timeline_path}")

    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline_data = json.load(f)

    # Determine master audio duration
    audio_duration = 20.0
    if os.path.exists(audio_meta_path):
        try:
            with open(audio_meta_path, "r", encoding="utf-8") as f:
                audio_meta = json.load(f)
                audio_duration = float(audio_meta.get("duration_seconds", 20.0))
        except Exception:
            pass
    elif "total_duration_seconds" in timeline_data:
        audio_duration = float(timeline_data["total_duration_seconds"])

    # Load B-Roll Catalog to resolve Drive IDs
    catalog_files = []
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat = json.load(f)
                catalog_files = cat.get("raw_files", [])
        except Exception:
            pass

    scenes = timeline_data.get("timeline", [])
    if not scenes:
        raise ValueError("Timeline has no scenes.")

    # Calculate original total planned duration across cuts
    original_durations = []
    for s in scenes:
        st = float(s.get("start_time", 0.0))
        et = float(s.get("end_time", st + 2.5))
        dur = max(0.5, et - st)
        original_durations.append(dur)

    orig_total = sum(original_durations)
    scaling_factor = audio_duration / orig_total if orig_total > 0 else 1.0

    fitted_scenes = []
    current_time = 0.0

    # Sequential serial numbering
    serial_map = {}
    counter = 1

    for idx, (scene, orig_dur) in enumerate(zip(scenes, original_durations), start=1):
        scaled_dur = orig_dur * scaling_factor
        start_time = round(current_time, 2)
        end_time = round(current_time + scaled_dur, 2)
        current_time = end_time

        orig_b_roll = scene.get("b_roll", f"clip_{idx}.mp4")
        if orig_b_roll not in serial_map:
            prefix = String = f"{counter:02d}"
            serial_name = f"{prefix}_{orig_b_roll}"
            
            # Match with catalog for file_id
            matched = next(
                (f for f in catalog_files if f["name"] == orig_b_roll or f["name"].lower() == orig_b_roll.lower()),
                None
            )
            file_id = matched["id"] if matched else None

            serial_map[orig_b_roll] = {
                "file_id": file_id,
                "file_name": serial_name,
                "original_name": orig_b_roll
            }
            counter += 1

        assigned = serial_map[orig_b_roll]

        fitted_scenes.append({
            "scene": scene.get("scene", idx),
            "start_time": start_time,
            "end_time": end_time,
            "duration": round(end_time - start_time, 2),
            "b_roll": assigned["file_name"],
            "original_b_roll": orig_b_roll,
            "text_overlay": scene.get("text_overlay", "")
        })

    # Ensure last scene aligns cleanly with target duration
    if fitted_scenes:
        fitted_scenes[-1]["end_time"] = round(audio_duration, 2)
        fitted_scenes[-1]["duration"] = round(fitted_scenes[-1]["end_time"] - fitted_scenes[-1]["start_time"], 2)

    fitted_payload = {
        "video_title": timeline_data.get("video_title", "Untitled Ad"),
        "total_duration_seconds": round(audio_duration, 2),
        "voiceover_script": timeline_data.get("voiceover_script", ""),
        "timeline": fitted_scenes
    }

    with open(output_timeline_path, "w", encoding="utf-8") as f:
        json.dump(fitted_payload, f, indent=2)

    # Save download queue for n8n Drive download step
    download_queue = list(serial_map.values())
    with open(download_queue_path, "w", encoding="utf-8") as f:
        json.dump(download_queue, f, indent=2)

    print(f"[FitTimeline] Successfully scaled {len(fitted_scenes)} scenes to {audio_duration:.2f}s", file=sys.stderr)

    res = {
        "status": "success",
        "fitted_timeline_path": output_timeline_path,
        "target_duration": round(audio_duration, 2),
        "download_count": len(download_queue)
    }
    sys.stdout.flush()
    print(json.dumps(res))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pro-rate and fit timeline cuts to exact audio length")
    parser.add_argument("--run-dir", required=True, help="Path to current run directory")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    fit_timeline(run_dir=args.run_dir, config_path=args.config)
