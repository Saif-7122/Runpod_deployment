# Content Engine

Raw footage in Google Drive → finished 9:16 reels (30-40 s, English or Telugu, captions, end card, post caption)
in the Drive OUTPUT folder. Target: ~50 videos per hour on one RunPod RTX 4090.

**Editors:** read [EDITORS_GUIDE.md](EDITORS_GUIDE.md) - one web form, no coding.

## How it works

| Step | Tool | Cost |
| --- | --- | --- |
| Clip analysis (once per clip, cached) | quality checks (code) + Claude Haiku vision; Sarvam speech-to-text for clips with speech | ~$0.005 per clip, once |
| Scripts: 5 versions per video in one call | Claude Sonnet, prompt cached, 10-step plan + editing rules (`styles/`) | ~$0.07 per video |
| Auto-repair + rule checks + fact check | code | free |
| Script judge: ranks the 5 | Claude Haiku | ~$0.003 |
| Voice | Sarvam bulbul:v3 (pace 1.1, +0.8 semitone pitch), English / Telugu | Sarvam per character |
| Draft + video judge (attention checks + Haiku viewer score) | ffmpeg/OpenCV + Claude Haiku | ~$0.002 |
| Final render (NVENC, brand fonts, safe zones) + upload | GPU | free |

Each batch prints its Claude spend and stops at `batch.max_claude_usd` (config.yaml).

## Admin: new pod

1. RunPod: RTX 4090, PyTorch template (CUDA 12.x), 150 GB+ volume, **expose HTTP port 5678**.
2. Web Terminal:
   ```bash
   cd /workspace && git clone https://github.com/Saif-7122/Runpod_deployment.git . && bash setup.sh
   ```
3. Upload `.env`, `token.json`, `client_secret.json` into `/workspace` (Jupyter file upload or `runpodctl send`).
4. First time only - build the clip catalog (long for the full library; only new clips are processed later):
   ```bash
   source /workspace/ce_env.sh && python3 analyze.py --drive
   ```
5. `bash /workspace/start.sh` → prints the editors' form link.

## Files

`analyze.py` clip analysis · `director.py` scripts · `repair.py` free fixes · `judge.py` rules + ranking ·
`tts.py` Sarvam voice · `fit_timeline.py` timing + captions · `render.py` ffmpeg · `video_judge.py` draft checks ·
`run.py` batch runner · `make_videos.sh` one-command wrapper · `n8n_blueprint.json` editors' form ·
`styles/*.yaml` style packs · `brief.json` project facts · `config.yaml` settings · `LICENSES.md`
