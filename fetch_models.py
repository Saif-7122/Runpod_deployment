"""Pre-download local model weights with retries (flaky networks drop Hugging Face connections).

  python fetch_models.py ResembleAI/chatterbox Qwen/Qwen3-4B
"""
import os
import sys
import time

os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")          # plain HTTP: the Xet protocol is dropped on some networks
from huggingface_hub import snapshot_download  # noqa: E402

for repo in sys.argv[1:]:
    for attempt in range(1, 9):
        try:
            path = snapshot_download(repo, allow_patterns=["*.json", "*.safetensors", "*.pt", "*.txt", "*.model", "*.tiktoken", "*.yaml"], max_workers=1)
            print(f"OK {repo} -> {path}", flush=True)
            break
        except Exception as e:
            print(f"{repo}: attempt {attempt} failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(5 * attempt)
    else:
        sys.exit(f"FAILED to download {repo}")
