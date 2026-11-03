"""Replace the Elite 18 9:16 and 16:9 files in 'elite 18 meta ads' with the approved v2 versions.
Old files go to the Drive trash (recoverable 30 days). 1:1 files are not touched."""
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN = Path(r"D:\Runpod_deployment\ads\work\t35\token_hoi.json")
FOLDER = "1hXXzr7xhf4cpGfP70ekGaTk5AtNtQjqM"
V2 = Path(r"D:\Runpod_deployment\ads\work\e18\v2")

creds = None
try:
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
except Exception:
    creds = None
if not (creds and creds.valid):
    flow = InstalledAppFlow.from_client_secrets_file(r"D:\Runpod_deployment\client_secret.json", SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=True, prompt="consent",
                                  authorization_prompt_message="Sign in as houseofinvestors9: {url}")
    TOKEN.write_text(creds.to_json())
svc = build("drive", "v3", credentials=creds, cache_discovery=False)

new = sorted(V2.glob("E18_*_9x16.png")) + sorted(V2.glob("E18_*_16x9.png"))
assert len(new) == 20, len(new)
names = {p.name for p in new}
live = svc.files().list(q=f"'{FOLDER}' in parents and trashed=false", fields="files(id,name)", pageSize=200).execute().get("files", [])
for f in live:
    if f["name"] in names:  # exact name match only, never touches 1x1
        svc.files().update(fileId=f["id"], body={"trashed": True}).execute()
        print("trashed", f["name"], flush=True)
for p in new:
    svc.files().create(body={"name": p.name, "parents": [FOLDER]},
                       media_body=MediaFileUpload(str(p), mimetype="image/png", resumable=True),
                       fields="id").execute()
    print("uploaded", p.name, flush=True)
print("DONE")
