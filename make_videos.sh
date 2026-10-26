#!/bin/bash
# One command for the whole pipeline (used by the n8n form; editors never need to type this).
#   ./make_videos.sh <how_many> <languages: "en te hi" | en | te | hi ...> [style] [analyse_new_clips: yes|no]
set -e
source /workspace/ce_env.sh
cd "$(dirname "$0")"
N="${1:-10}"; LANGS="${2:-en te hi}"; STYLE="${3:-weekend_home}"; ANALYSE="${4:-no}"
LOG=/workspace/data/last_run.log
echo "[$(date '+%F %T')] start: $N videos, languages: $LANGS, style: $STYLE, analyse: $ANALYSE" | tee "$LOG"
if [ "$ANALYSE" = "yes" ]; then
  python3 analyze.py --drive >> "$LOG" 2>&1          # only new clips are analysed; old ones are cached
fi
python3 run.py --brief brief.json --style "$STYLE" --variants "$N" --languages $LANGS --upload --cleanup >> "$LOG" 2>&1
echo "[$(date '+%F %T')] finished - videos and captions are in the Drive OUTPUT folder" | tee -a "$LOG"
