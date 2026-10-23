import os
import sys
import json
import argparse
import shutil
import yaml
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips
)

def load_yaml(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def render_video(run_dir, config_path="config.yaml"):
    config = load_yaml(config_path)
    dirs = config.get("directories", {})
    cache_dir = dirs.get("cache", "/workspace/cache")
    render_conf = config.get("rendering", {})

    v_codec = render_conf.get("video_codec", "h264_nvenc")
    fallback_v_codec = render_conf.get("fallback_video_codec", "libx264")
    a_codec = render_conf.get("audio_codec", "aac")
    fps = render_conf.get("fps", 30)
    preset = render_conf.get("preset", "fast")
    threads = render_conf.get("threads", 8)
    font_name = render_conf.get("font", "Liberation-Sans-Bold")
    fontsize = render_conf.get("fontsize", 70)
    font_color = render_conf.get("font_color", "white")
    stroke_color = render_conf.get("stroke_color", "black")
    stroke_width = render_conf.get("stroke_width", 2)

    assets_dir = os.path.join(run_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # 1. Load timeline (prefer fitted_timeline.json)
    timeline_path = os.path.join(run_dir, "fitted_timeline.json")
    if not os.path.exists(timeline_path):
        timeline_path = os.path.join(run_dir, "timeline.json")
    if not os.path.exists(timeline_path):
        raise FileNotFoundError(f"Timeline JSON not found in {run_dir}")

    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline_data = json.load(f)

    # 2. Locate master audio
    audio_path = os.path.join(run_dir, "clean_audio.wav")
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        audio_path = os.path.join(run_dir, "raw_tts.wav")

    # 3. Process scenes
    scenes = timeline_data.get("timeline", [])
    if not scenes:
        raise ValueError("Timeline has no scenes to render.")

    processed_clips = []
    opened_clips = []
    master_audio = None

    try:
        for idx, scene in enumerate(scenes, start=1):
            b_roll = scene.get("b_roll")
            orig_b_roll = scene.get("original_b_roll", b_roll)

            # Check run assets, then cache directory
            asset_path = os.path.join(assets_dir, b_roll)
            if not os.path.exists(asset_path):
                cache_candidate = os.path.join(cache_dir, orig_b_roll)
                if os.path.exists(cache_candidate):
                    shutil.copy2(cache_candidate, asset_path)
                elif os.path.exists(os.path.join("/workspace/assets", b_roll)):
                    shutil.copy2(os.path.join("/workspace/assets", b_roll), asset_path)

            if not os.path.exists(asset_path):
                # In testing, create a blank color clip placeholder if clip is missing
                print(f"[Render] Warning: Asset {asset_path} missing. Creating fallback color clip.", file=sys.stderr)
                from moviepy.editor import ColorClip
                req_dur = max(0.5, float(scene.get("end_time", 2.5)) - float(scene.get("start_time", 0.0)))
                subclip = ColorClip(size=(1080, 1920), color=(20, 40, 20), duration=req_dur)
            else:
                v_clip = VideoFileClip(asset_path)
                opened_clips.append(v_clip)
                st = float(scene.get("start_time", 0.0))
                et = float(scene.get("end_time", 0.0))
                req_dur = max(0.1, et - st)
                safe_dur = min(req_dur, v_clip.duration)
                subclip = v_clip.subclip(0, safe_dur)

            # Add TextClip overlay
            overlay_text = str(scene.get("text_overlay", "")).strip()
            if overlay_text:
                txt_clip = (
                    TextClip(
                        overlay_text,
                        font=font_name,
                        fontsize=fontsize,
                        color=font_color,
                        stroke_color=stroke_color,
                        stroke_width=stroke_width
                    )
                    .set_duration(subclip.duration)
                    .set_position("center")
                )
                scene_clip = CompositeVideoClip([subclip, txt_clip])
            else:
                scene_clip = subclip

            processed_clips.append(scene_clip)

        # 4. Concatenate scenes
        final_video = concatenate_videoclips(processed_clips, method="compose")

        # 5. Attach audio
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            master_audio = AudioFileClip(audio_path)
            target_dur = min(master_audio.duration, final_video.duration)
            final_video = final_video.subclip(0, target_dur)
            final_audio = master_audio.subclip(0, target_dur)
            final_video = final_video.set_audio(final_audio)
        else:
            target_dur = final_video.duration

        output_video_path = os.path.join(run_dir, "finished_ad.mp4")
        output_project_path = os.path.join(run_dir, "edit_project_source.json")

        # 6. Render with NVENC hardware acceleration
        print(f"[Render] Encoding with {v_codec} to {output_video_path}...", file=sys.stderr)
        try:
            final_video.write_videofile(
                output_video_path,
                codec=v_codec,
                audio_codec=a_codec,
                fps=fps,
                preset=preset,
                threads=threads
            )
        except Exception as e:
            print(f"[Render] Hardware encoding failed ({e}). Falling back to {fallback_v_codec}...", file=sys.stderr)
            final_video.write_videofile(
                output_video_path,
                codec=fallback_v_codec,
                audio_codec=a_codec,
                fps=fps,
                preset=preset,
                threads=threads
            )

        # 7. Write Edit Project Source JSON
        source_files = sorted([f for f in os.listdir(assets_dir) if os.path.isfile(os.path.join(assets_dir, f))])
        project_source = {
            "video_title": timeline_data.get("video_title", "Untitled Ad"),
            "total_duration_seconds": round(target_dur, 2),
            "voiceover_script": timeline_data.get("voiceover_script", ""),
            "timeline": timeline_data.get("timeline", []),
            "source_files": source_files,
            "instructions_for_editors": (
                "This editable project source file maps the serial-numbered timeline to the source video clips stored in this run's assets folder. "
                "Each scene references the exact serial-numbered b_roll file. Editors can import these assets and timeline timings into "
                "Adobe Premiere Pro, DaVinci Resolve, or Final Cut Pro for final color grading, transitions, and audio mastering."
            )
        }

        with open(output_project_path, "w", encoding="utf-8") as f:
            json.dump(project_source, f, indent=2)

        result = {
            "status": "success",
            "video_path": output_video_path,
            "project_source_path": output_project_path,
            "duration": round(target_dur, 2)
        }
        sys.stdout.flush()
        print(json.dumps(result))

    finally:
        for c in opened_clips:
            try:
                c.close()
            except Exception:
                pass
        if master_audio:
            try:
                master_audio.close()
            except Exception:
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render Ad Video using GPU NVENC")
    parser.add_argument("--run-dir", required=True, help="Path to current run directory")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    render_video(run_dir=args.run_dir, config_path=args.config)
