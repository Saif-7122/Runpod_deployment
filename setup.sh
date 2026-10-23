#!/bin/bash
echo "Starting High-Performance Video Factory Setup..."

# 1. Update Ubuntu and install core video processing tools
apt-get update && apt-get install -y ffmpeg curl wget

# 2. Install Node.js (Required for n8n)
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# 3. Install n8n globally
echo "Installing n8n..."
npm install -g n8n

# 4. Install Cloudflare Tunnels (Solves the Dynamic URL issue for Google OAuth)
echo "Installing Cloudflare Tunnels..."
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb 
dpkg -i cloudflared-linux-amd64.deb

# 5. Install Python Machine Learning & API dependencies
# Added 'openai' for the AI Judge and 'elevenlabs' for the Audio TTS
echo "Installing Python Libraries (Whisper, Anthropic, OpenAI, ElevenLabs)..."
pip install faster-whisper anthropic openai elevenlabs python-dotenv

echo "======================================================="
echo "SETUP COMPLETE! ALL ENGINES GO."
echo "======================================================="
echo ""
echo "NEXT STEPS:"
echo "1. Type 'n8n start --tunnel' (or just 'n8n') and let it run."
echo "2. Open a SECOND terminal window and run:"
echo "   cloudflared tunnel --url http://localhost:5678"
echo "3. Copy the .trycloudflare.com link it gives you and paste it into Google Cloud!"