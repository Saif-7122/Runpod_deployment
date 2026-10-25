#!/bin/bash
# Content Engine v1.2 - RunPod RTX 4090 setup (PyTorch CUDA 12.x template).
# Usage (repo cloned into /workspace):   bash setup.sh            # pipeline only
#                                        INSTALL_N8N=1 bash setup.sh   # + n8n
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
echo "   local GPU models (voice, vision, speech-to-text)"
pip install -q -r "$REPO_DIR/requirements-gpu.txt"
export HF_HOME=/workspace/hf_cache          # model weights persist on the volume between pod restarts

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

echo "== 5/5 n8n (optional)"
if [ "${INSTALL_N8N:-0}" = "1" ]; then
  if ! command -v node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
    apt-get install -y -qq nodejs >/dev/null
  fi
  npm install -g n8n >/dev/null
  cat > /workspace/start_n8n.sh <<'EOF'
#!/bin/bash
source /workspace/ce_env.sh
export NODES_EXCLUDE="[]"
export NODE_FUNCTION_ALLOW_BUILTIN=fs,path,child_process
n8n start
EOF
  chmod +x /workspace/start_n8n.sh
  echo "   start with /workspace/start_n8n.sh (reach it via ssh -L 5678:localhost:5678)"
fi

[ -f "$REPO_DIR/.env" ] || echo "!! Create $REPO_DIR/.env from .env.example before running."
echo "== DONE. Next:  source /workspace/ce_env.sh && cd $REPO_DIR && python3 analyze.py --drive --limit 3"
