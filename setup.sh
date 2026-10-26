#!/bin/bash
# Content Engine - RunPod RTX 4090 setup (PyTorch CUDA 12.x template). Run once per new pod:
#   cd /workspace && git clone https://github.com/Saif-7122/Runpod_deployment.git . && bash setup.sh
# Then every time the pod starts:  bash /workspace/start.sh   (prints the form link for the editors)
set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${CE_WORKSPACE:-/workspace/data}"
BIN_DIR="/workspace/bin"
mkdir -p "$DATA_DIR" "$BIN_DIR"

echo "== 1/5 system packages"
apt-get update -qq
apt-get install -y -qq --no-install-recommends ffmpeg fonts-liberation curl xz-utils git python3-pip >/dev/null

echo "== 2/5 NVENC check"
nvenc_ok() {
  "$1" -hide_banner -loglevel error -f lavfi -i testsrc=duration=2:size=1080x1920:rate=30 \
       -c:v h264_nvenc -preset p5 -cq 21 -f null - 2>/dev/null
}
FFMPEG="$(command -v ffmpeg)"
if nvenc_ok "$FFMPEG"; then
  echo "   system ffmpeg has working NVENC"
else
  echo "   system ffmpeg lacks NVENC -> downloading static build with NVENC"
  curl -fsSL -o /tmp/ffmpeg.tar.xz \
    https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
  tar -xJf /tmp/ffmpeg.tar.xz -C /tmp
  cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe "$BIN_DIR/"
  FFMPEG="$BIN_DIR/ffmpeg"
  if nvenc_ok "$FFMPEG"; then
    echo "   static ffmpeg NVENC OK"
  else
    echo "!! NVENC still not working. Check nvidia-smi and that the pod exposes video encode"
    echo "!! (NVIDIA_DRIVER_CAPABILITIES must include 'video'). Try another pod/region."
    exit 1
  fi
fi

echo "== 3/5 python packages"
pip install -q --upgrade pip
pip install -q -r "$REPO_DIR/requirements.txt"
if [ "${INSTALL_LOCAL_MODELS:-0}" = "1" ]; then     # not used in production (Claude + Sarvam)
  pip install -q -r "$REPO_DIR/requirements-gpu.txt"
fi

echo "== 4/5 environment file"
cat > /workspace/ce_env.sh <<EOF
export CE_WORKSPACE="$DATA_DIR"
export CE_CODEC=h264_nvenc
export CE_HW_DECODE=1
export FFMPEG_BIN="$FFMPEG"
export N8N_USER_FOLDER=/workspace/.n8n
export HF_HOME=/workspace/hf_cache
EOF
grep -q ce_env.sh ~/.bashrc 2>/dev/null || echo "source /workspace/ce_env.sh" >> ~/.bashrc

echo "== 5/5 n8n + the editors' form"
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi
command -v n8n >/dev/null 2>&1 || npm install -g n8n@1 >/dev/null
chmod +x "$REPO_DIR/make_videos.sh"
cat > /workspace/start.sh <<'EOF'
#!/bin/bash
# Start the editors' form. Run this every time the pod starts.
source /workspace/ce_env.sh
export NODES_EXCLUDE="[]"
export NODE_FUNCTION_ALLOW_BUILTIN=fs,path,child_process
export N8N_RUNNERS_ENABLED=false
URL="https://${RUNPOD_POD_ID}-5678.proxy.runpod.net"
export WEBHOOK_URL="$URL/" N8N_EDITOR_BASE_URL="$URL/" N8N_PROXY_HOPS=1
n8n import:workflow --input=/workspace/n8n_blueprint.json >/dev/null 2>&1
WID=$(n8n export:workflow --all 2>/dev/null | python3 -c "import sys,json; r=sys.stdin.read(); d=json.loads(r[r.index('['):]); print(next(w['id'] for w in d if w['name'].startswith('Make Oxygen Forest reels')))" 2>/dev/null)
[ -n "$WID" ] && n8n update:workflow --id="$WID" --active=true >/dev/null 2>&1
pkill -f "n8n start" 2>/dev/null; sleep 1
nohup n8n start > /workspace/data/n8n.log 2>&1 &
sleep 8
echo ""
echo "=================================================================="
echo "  EDITORS' FORM:  $URL/form/oxygen-forest-reels"
echo "  Videos land in the Drive OUTPUT folder. Progress log: /workspace/data/last_run.log"
echo "=================================================================="
EOF
chmod +x /workspace/start.sh
echo "   expose HTTP port 5678 on the pod, then run: bash /workspace/start.sh"

[ -f "$REPO_DIR/.env" ] || echo "!! Create $REPO_DIR/.env from .env.example before running."
echo "== DONE. Next: copy .env + token.json + client_secret.json into $REPO_DIR, then: bash /workspace/start.sh"
