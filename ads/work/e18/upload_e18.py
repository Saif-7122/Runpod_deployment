"""Upload the Elite 18 finals (1:1, 9:16, 16:9) to the 'elite 18 meta ads' Drive folder."""
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN = Path(r"D:\Runpod_deployment\ads\work\t35\token_hoi.json")
FOLDER = "1hXXzr7xhf4cpGfP70ekGaTk5AtNtQjqM"
FINAL = Path(r"D:\Runpod_deployment\ads\work\e18\final")

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
done = {f["name"] for f in svc.files().list(q=f"'{FOLDER}' in parents and trashed=false", fields="files(name)", pageSize=200).execute().get("files", [])}
for p in sorted(FINAL.glob("E18_*.png")):
    if p.name in done:
        print("skip", p.name); continue
    svc.files().create(body={"name": p.name, "parents": [FOLDER]},
                       media_body=MediaFileUpload(str(p), mimetype="image/png", resumable=True),
                       fields="id").execute()
    print("uploaded", p.name, flush=True)
print("DONE")
