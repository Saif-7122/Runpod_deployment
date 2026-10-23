# Content Engine v1.2

Raw property clips in Google Drive → finished, captioned, voiced 9:16 ads.
Every clip is watched once (quality per 0.25 s + Claude vision), cut into approved segments,
and Claude writes each ad from what the footage actually shows.

| Script | Does |
| --- | --- |
| `analyze.py` | Watches raw clips: shot cuts, blur, shake, exposure, then Claude vision → `catalog.json` + `summary.md` |
| `director.py` | Claude writes `script.json` (lines + chosen segments, no times) |
| `judge.py` | Rule checks, then Claude rubric (`brand_voice_rubric.md`); 3 attempts max |
| `tts.py` | Sarvam voice per sentence, silence-trimmed, joined |
| `fit_timeline.py` | Scene times from measured audio, in-points inside approved segments, `captions.ass` |
| `render.py` | One ffmpeg command → 1080×1920 MP4 (NVENC on the pod, x264 locally) |
| `run.py` | All of the above for N variants in parallel, optional Drive upload |
| `drive.py` | Drive list / download / upload, `python drive.py login` for OAuth |

## 1. Local test (laptop)

```bash
pip install -r requirements.txt
copy .env.example .env          # then fill in the keys
python drive.py login           # once; opens a browser, writes token.json
python drive.py ls 12sr-Z52Cc50QifU3-3qfDQpXAt4DevNi
python analyze.py --drive --limit 5
```

Open `workspace/catalog/summary.md`: approved segments per project, grouped by shot type, with reasons for every reject. Tune `thresholds_clip` in `config.yaml` until it matches your eye, then:

```bash
python run.py --brief brief.json              # one video, written to workspace/runs/<run_id>/
python run.py --brief brief.json --variants 3 # three different angles
```

`brief.json` → `project` must match the Drive subfolder name of the clips (falls back to all clips).

## 2. RunPod (RTX 4090)

```bash
cd /workspace
git clone https://github.com/Saif-7122/Runpod_deployment.git .
bash setup.sh                   # INSTALL_N8N=1 bash setup.sh to add n8n
# copy .env and token.json from your laptop into /workspace
source /workspace/ce_env.sh
python3 analyze.py --drive
python3 run.py --brief brief.json --variants 50 --parallel 8 --upload --cleanup
```

`setup.sh` verifies NVENC with a test encode and stops if the GPU encoder is not available.

## Before the first real run

- Set `drive.output_folder_id` (your `04_Ready` folder) in `config.yaml`.
- Check the Sarvam model and speaker names in `config.yaml` (`tts.model`, `tts.speaker`) against your Sarvam dashboard.
- The first `analyze.py` run on a project: review `summary.md` and adjust thresholds.
