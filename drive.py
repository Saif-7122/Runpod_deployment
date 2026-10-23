"""Google Drive: list raw clips, download them, upload finished videos.

Auth (pick one, set in .env):
  GOOGLE_OAUTH_CLIENT_FILE=client_secret.json   -> user OAuth (recommended; can upload to My Drive)
  GOOGLE_TOKEN_FILE=token.json                   -> where the OAuth token is stored
  GOOGLE_SERVICE_ACCOUNT_FILE=sa.json            -> service account (share folders with its email;
                                                    uploads only work into a Shared Drive)

First OAuth login (run on your laptop, it opens a browser):
  python drive.py login
Then copy token.json to the pod next to this file.
"""
import io
import os
import sys
from pathlib import Path

from common import ROOT, log

SCOPES = ["https://www.googleapis.com/auth/drive"]
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts")
FOLDER_MIME = "application/vnd.google-apps.folder"

import threading
_local = threading.local()      # the Google HTTP client is not thread-safe: one service per thread


def _path(env, default):
    p = Path(os.environ.get(env, default))
    return p if p.is_absolute() else ROOT / p


def _credentials(interactive=False):
    sa = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if sa:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(_path("GOOGLE_SERVICE_ACCOUNT_FILE", sa), scopes=SCOPES)

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    token = _path("GOOGLE_TOKEN_FILE", "token.json")
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json())
    if creds and creds.valid:
        return creds
    if not interactive:
        raise RuntimeError("No valid Google token. Run `python drive.py login` on a machine with a browser.")
    from google_auth_oauthlib.flow import InstalledAppFlow
    client = _path("GOOGLE_OAUTH_CLIENT_FILE", "client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=True,
                                  authorization_prompt_message="Open this URL to allow Drive access: {url}")
    token.write_text(creds.to_json())
    return creds


def service():
    if getattr(_local, "svc", None) is None:
        from googleapiclient.discovery import build
        _local.svc = build("drive", "v3", credentials=_credentials(), cache_discovery=False)
    return _local.svc


def _list_children(folder_id):
    q = f"'{folder_id}' in parents and trashed = false"
    page = None
    while True:
        resp = service().files().list(
            q=q, pageSize=1000, pageToken=page,
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, md5Checksum)",
            supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        yield from resp.get("files", [])
        page = resp.get("nextPageToken")
        if not page:
            break


def list_videos(root_folder_id):
    """All video files under the folder, recursively.
    project = name of the first-level subfolder (or the root folder's name for loose files)."""
    root_name = service().files().get(fileId=root_folder_id, fields="name", supportsAllDrives=True).execute()["name"]
    out = []
    stack = [(root_folder_id, None, "")]
    while stack:
        fid, project, rel = stack.pop()
        for f in _list_children(fid):
            if f["mimeType"] == FOLDER_MIME:
                stack.append((f["id"], project or f["name"], f"{rel}{f['name']}/"))
            elif f["name"].lower().endswith((".lrf", ".thm")):
                continue        # DJI low-res duplicates / thumbnails of the real .MP4
            elif f["name"].lower().endswith(VIDEO_EXT) or f["mimeType"].startswith("video/"):
                f["project"] = project or root_name
                f["drive_path"] = rel + f["name"]
                out.append(f)
    log("drive", f"found {len(out)} video files under '{root_name}'")
    return out


def download(file_id, dest):
    from googleapiclient.http import MediaIoBaseDownload
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = service().files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(tmp, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=64 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
    os.replace(tmp, dest)
    return dest


def upload(path, folder_id, name=None, mime="video/mp4"):
    from googleapiclient.http import MediaFileUpload
    path = Path(path)
    media = MediaFileUpload(str(path), mimetype=mime, resumable=True, chunksize=32 * 1024 * 1024)
    meta = {"name": name or path.name, "parents": [folder_id]}
    f = service().files().create(body=meta, media_body=media, fields="id, webViewLink",
                                 supportsAllDrives=True).execute()
    return f


def ensure_folder(parent_id, name):
    for f in _list_children(parent_id):
        if f["mimeType"] == FOLDER_MIME and f["name"] == name:
            return f["id"]
    f = service().files().create(body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
                                 fields="id", supportsAllDrives=True).execute()
    return f["id"]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        _credentials(interactive=True)
        print("Google login OK, token saved.")
    elif len(sys.argv) > 2 and sys.argv[1] == "ls":
        for v in list_videos(sys.argv[2]):
            print(f"{v['project']:<25} {v['drive_path']:<60} {int(v.get('size', 0)) / 1e6:8.1f} MB")
    else:
        print("usage: python drive.py login | python drive.py ls <folder_id>")
