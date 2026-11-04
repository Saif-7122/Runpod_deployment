"""Print the newest Signal Feed docs from the news folder as plain text (no Drive connector needed).

  python daily_content/fetch_feed.py [--n 1]
Auth: drive.py (token.json, or GOOGLE_TOKEN_JSON env).
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import drive  # noqa: E402

NEWS_FOLDER = os.environ.get("NEWS_FOLDER_ID", "1fhCDLbTeJ1-ZmtN9HZ6MLgF716tGLf13")

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=1, help="how many of the newest feeds to print")
a = ap.parse_args()
svc = drive.service()
files = svc.files().list(q=f"'{NEWS_FOLDER}' in parents and trashed=false and name contains 'Signal Feed'",
                         orderBy="createdTime desc", pageSize=a.n, fields="files(id,name)",
                         supportsAllDrives=True, includeItemsFromAllDrives=True).execute()["files"]
for f in files:
    text = svc.files().export(fileId=f["id"], mimeType="text/plain").execute().decode("utf-8")
    print(f"===== {f['name']} =====\n{text}\n")
