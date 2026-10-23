import subprocess
import os

def render_video(input_video, output_video, text_hook):
    font_path = "bold_font.ttf" # We will upload a TTF font file tomorrow
    
    # NVENC is the RTX 4090's dedicated video encoding chip
    ffmpeg_cmd = [
        'ffmpeg', '-y', 
        '-hwaccel', 'cuda', # Force FFmpeg to use the GPU for decoding
        '-i', input_video,
        '-vf', f"drawtext=fontfile='{font_path}':text='{text_hook}':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2:borderw=4:bordercolor=black",
        '-c:a', 'copy', 
        '-c:v', 'h264_nvenc', # Encode using the RTX 4090 hardware
        '-preset', 'p6',      # Nvidia preset for high quality/speed balance
        '-b:v', '5M',         # 5 Mbps bitrate for clean Snapchat/Reels quality
        output_video
    ]
    
    print(f"Sending {input_video} to RTX 4090...")
    subprocess.run(ffmpeg_cmd)
    print(f"Finished rendering: {output_video}")

# Tomorrow, we will map this to read Claude's JSON output
render_video("raw_drone_shot.mp4", "oxygen_forest_snap_1.mp4", "Buy A Plot At Oxygen Forest!")