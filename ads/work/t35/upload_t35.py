"""One-off: upload the T35 final PNGs into the 'T35 meta ad images' Drive folder.
Uses a separate token file so the reel engine's token.json is untouched."""
import os, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT = Path(r"D:\Runpod_deployment")
TOKEN = ROOT / "ads" / "work" / "t35" / "token_hoi.json"
FOLDER = "14zhROytV0PBO5rIdLkZMYQvJULS8pMiD"
FINAL = ROOT / "ads" / "work" / "t35" / "final"

creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
if not (creds and creds.valid):
    flow = InstalledAppFlow.from_client_secrets_file(str(ROOT / "client_secret.json"), SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=True,
                                  authorization_prompt_message="Sign in as houseofinvestors9 to allow Drive upload: {url}")
TOKEN.write_text(creds.to_json())
svc = build("drive", "v3", credentials=creds, cache_discovery=False)
done = {f["name"] for f in svc.files().list(q=f"'{FOLDER}' in parents and trashed=false", fields="files(name)", pageSize=200).execute().get("files", [])}
for p in sorted(FINAL.glob("T35_*.png")):
    if p.name in done:
        print("skip", p.name); continue
    svc.files().create(body={"name": p.name, "parents": [FOLDER]},
                       media_body=MediaFileUpload(str(p), mimetype="image/png", resumable=True),
                       fields="id").execute()
    print("uploaded", p.name, flush=True)
print("DONE")
