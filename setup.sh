#!/bin/bash
set -e

echo "======================================================="
echo "Starting RunPod RTX 4090 Video Factory Setup..."
echo "======================================================="

# 1. Update Ubuntu and install FFmpeg, ImageMagick, Liberation Fonts, and build tools
echo "Installing system packages (ffmpeg, imagemagick, fonts-liberation, curl, wget)..."
apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    curl \
    wget \
    gnupg \
    build-essential

# 2. Fix ImageMagick security policy for MoviePy TextClip rendering
echo "Fixing ImageMagick policy for TextClip..."
if [ -f /etc/ImageMagick-6/policy.xml ]; then
    sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<!-- <policy domain="path" rights="none" pattern="@\*" -->/' /etc/ImageMagick-6/policy.xml || true
    sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml || true
fi
if [ -f /etc/ImageMagick-7/policy.xml ]; then
    sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<!-- <policy domain="path" rights="none" pattern="@\*" -->/' /etc/ImageMagick-7/policy.xml || true
    sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-7/policy.xml || true
fi

# 3. Install Node.js (v20.x) and npm
echo "Installing Node.js 20.x and npm..."
if ! command -v node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# 4. Install n8n globally
echo "Installing n8n globally..."
npm install -g n8n

# 5. Install Python ML and Video Editing libraries
echo "Installing Python libraries (torch, transformers, accelerate, moviepy==1.0.3, auto-editor, pydantic)..."
pip install --upgrade pip
pip install \
    torch \
    transformers \
    accelerate \
    "moviepy==1.0.3" \
    auto-editor \
    pydantic \
    python-dotenv

# 6. Create standard workspace directories
echo "Creating workspace directories: /workspace/inputs, /workspace/outputs, /workspace/assets..."
mkdir -p /workspace/inputs /workspace/outputs /workspace/assets

# 7. Create helper startup script for n8n with required permissions for fs and path
echo "Creating /workspace/start_n8n.sh..."
cat << 'EOF' > /workspace/start_n8n.sh
#!/bin/bash
export NODES_EXCLUDE="[]"
export NODE_FUNCTION_ALLOW_BUILTIN=fs,path
n8n start
EOF

chmod +x /workspace/start_n8n.sh

echo "======================================================="
echo "SETUP COMPLETE! RunPod Environment Ready."
echo "======================================================="
echo "Launch n8n at any time with: /workspace/start_n8n.sh"