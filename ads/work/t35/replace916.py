"""Trash the old *_9x16.png files in the T35 Drive folder and upload the new ones from final916/.
Trash is recoverable for 30 days; nothing is permanently deleted."""
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT = Path(r"D:\Runpod_deployment\ads\work\t35")
FOLDER = "14zhROytV0PBO5rIdLkZMYQvJULS8pMiD"

from google_auth_oauthlib.flow import InstalledAppFlow
TOKEN = ROOT / "token_hoi.json"
creds = None
try:
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
except Exception:
    creds = None
if not (creds and creds.valid):
    flow = InstalledAppFlow.from_client_secrets_file(r"D:\Runpod_deployment\client_secret.json", SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=True, prompt="consent",
                                  authorization_prompt_message="Sign in as houseofinvestors9: {url}")
    TOKEN.write_text(creds.to_json())
svc = build("drive", "v3", credentials=creds, cache_discovery=False)

old = svc.files().list(q=f"'{FOLDER}' in parents and trashed=false and name contains '_9x16'",
                       fields="files(id,name)", pageSize=100).execute().get("files", [])
for f in old:
    svc.files().update(fileId=f["id"], body={"trashed": True}).execute()
    print("trashed", f["name"], flush=True)

for p in sorted((ROOT / "final916").glob("T35_*_9x16.png")):
    svc.files().create(body={"name": p.name, "parents": [FOLDER]},
                       media_body=MediaFileUpload(str(p), mimetype="image/png", resumable=True),
                       fields="id").execute()
    print("uploaded", p.name, flush=True)
print("DONE")
