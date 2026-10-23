import os
import sys
import json
import subprocess
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips
)

def render_ad():
    timeline_path = "/workspace/inputs/current_timeline.json"
    raw_audio_path = "/workspace/inputs/raw_tts.wav"
    clean_audio_path = "/workspace/inputs/clean_audio.wav"
    assets_dir = "/workspace/assets"
    output_video_path = "/workspace/outputs/finished_ad.mp4"
    output_project_path = "/workspace/outputs/edit_project_source.json"

    # Ensure required directories exist
    os.makedirs("/workspace/inputs", exist_ok=True)
    os.makedirs("/workspace/outputs", exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    print(f"[Editor] Loading timeline: {timeline_path}")
    if not os.path.exists(timeline_path):
        raise FileNotFoundError(f"Timeline JSON not found at {timeline_path}")

    with open(timeline_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Clean audio using auto-editor (fallback to raw_tts.wav if clean_audio.wav is not created)
    active_audio_path = raw_audio_path
    if os.path.exists(raw_audio_path):
        print(f"[Editor] Processing TTS with auto-editor: {raw_audio_path}")
        auto_cmd = [
            "auto-editor",
            raw_audio_path,
            "-o",
            clean_audio_path,
            "--margin",
            "0.1sec"
        ]
        subprocess.run(auto_cmd, check=False)
        if os.path.exists(clean_audio_path) and os.path.getsize(clean_audio_path) > 0:
            print(f"[Editor] Cleaned audio generated successfully: {clean_audio_path}")
            active_audio_path = clean_audio_path
        else:
            print(f"[Editor] clean_audio.wav not created. Falling back to {raw_audio_path}")
    else:
        print(f"[Editor] Warning: {raw_audio_path} not found.")

    timeline = data.get("timeline", [])
    if not timeline:
        raise ValueError("Timeline array is empty in current_timeline.json.")

    processed_clips = []
    opened_clips = []
    master_audio = None

    try:
        # 2. Build subclips and text overlays
        for idx, scene in enumerate(timeline, start=1):
            b_roll_filename = scene.get("b_roll")
            if not b_roll_filename:
                raise ValueError(f"Scene {scene.get('scene', idx)} has no 'b_roll' specified.")

            asset_file_path = os.path.join(assets_dir, b_roll_filename)
            if not os.path.exists(asset_file_path):
                raise FileNotFoundError(f"B-roll file not found in assets: {asset_file_path}")

            start_t = float(scene.get("start_time", 0.0))
            end_t = float(scene.get("end_time", 0.0))
            duration = max(0.1, end_t - start_t)

            print(f"[Editor] Processing scene {scene.get('scene', idx)}: {b_roll_filename} (requested duration: {duration:.2f}s)")
            video_clip = VideoFileClip(asset_file_path)
            opened_clips.append(video_clip)

            # Safely clamp subclip times so MoviePy never crashes if a Drive clip is shorter than end_time
            safe_duration = min(duration, video_clip.duration)
            subclip = video_clip.subclip(0, safe_duration)

            text_overlay = str(scene.get("text_overlay", "")).strip()
            if text_overlay:
                print(f"[Editor] Generating TextClip: '{text_overlay}'")
                txt_clip = (
                    TextClip(
                        text_overlay,
                        font='Liberation-Sans-Bold',
                        fontsize=70,
                        color='white',
                        stroke_color='black',
                        stroke_width=2
                    )
                    .set_duration(subclip.duration)
                    .set_position('center')
                )
                scene_clip = CompositeVideoClip([subclip, txt_clip])
            else:
                scene_clip = subclip

            processed_clips.append(scene_clip)

        # 3. Concatenate video clips
        print("[Editor] Concatenating scene clips...")
        final_video = concatenate_videoclips(processed_clips, method="compose")

        # 4. Attach Audio (clamped to min(master_audio.duration, final_video.duration))
        if os.path.exists(active_audio_path) and os.path.getsize(active_audio_path) > 0:
            print(f"[Editor] Loading master audio from {active_audio_path}")
            master_audio = AudioFileClip(active_audio_path)
            target_duration = min(master_audio.duration, final_video.duration)
            final_video = final_video.subclip(0, target_duration)
            final_audio = master_audio.subclip(0, target_duration)
            final_video = final_video.set_audio(final_audio)
        else:
            print("[Editor] Proceeding without audio track.")
            target_duration = final_video.duration

        # 5. Render Video with GPU NVENC acceleration
        print(f"[Editor] Rendering video to {output_video_path}...")
        try:
            final_video.write_videofile(
                output_video_path,
                codec="h264_nvenc",
                audio_codec="aac",
                fps=30,
                preset="fast",
                threads=8
            )
        except Exception as nvenc_err:
            print(f"[Editor] NVENC encoding failed ({nvenc_err}), falling back to libx264...")
            final_video.write_videofile(
                output_video_path,
                codec="libx264",
                audio_codec="aac",
                fps=30,
                preset="fast",
                threads=8
            )

        print(f"[Editor] Render successful: {output_video_path}")

        # 6. Save Editable Project Source JSON
        source_files = sorted([f for f in os.listdir(assets_dir) if os.path.isfile(os.path.join(assets_dir, f))])
        project_source = {
            "video_title": data.get("video_title", "Untitled Ad"),
            "total_duration_seconds": data.get("total_duration_seconds", target_duration),
            "voiceover_script": data.get("voiceover_script", ""),
            "timeline": data.get("timeline", []),
            "source_files": source_files,
            "instructions_for_editors": (
                "This editable project source file maps the serial-numbered timeline to the source video clips stored in /workspace/assets/. "
                "Each scene references the exact serial-numbered b_roll file. Editors can import these assets and timeline timings into "
                "Adobe Premiere Pro, DaVinci Resolve, or Final Cut Pro for final color grading, transitions, and audio mastering."
            )
        }

        with open(output_project_path, "w", encoding="utf-8") as f:
            json.dump(project_source, f, indent=2)

        print(f"[Editor] Editable project source saved: {output_project_path}")

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
    render_ad()