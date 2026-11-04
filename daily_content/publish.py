"""Upload one day's content to Drive: <output folder>/<date>/ with the copy as a Google Doc and the carousel PDF.

  python daily_content/publish.py --date 2026-11-04 --doc day.md --pdf carousel.pdf

Auth: drive.py (token.json, or GOOGLE_TOKEN_JSON env with its contents).
Output folder: DAILY_CONTENT_FOLDER_ID env (default: HOI Daily Content).
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import drive  # noqa: E402

OUTPUT_FOLDER = os.environ.get("DAILY_CONTENT_FOLDER_ID", "1PObUk5Z0GpFxYox2eI_b0_RtT_yVEqpz")


def upload_doc(md_path, folder_id, title):
    """Markdown -> native Google Doc (Drive converts it on upload)."""
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(md_path), mimetype="text/markdown", resumable=False)
    meta = {"name": title, "parents": [folder_id], "mimeType": "application/vnd.google-apps.document"}
    return drive.service().files().create(body=meta, media_body=media, fields="id, webViewLink",
                                          supportsAllDrives=True).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--pdf")
    a = ap.parse_args()
    day = drive.ensure_folder(OUTPUT_FOLDER, a.date)
    d = upload_doc(a.doc, day, f"{a.date} Content")
    print("doc:", d["webViewLink"])
    if a.pdf:
        p = drive.upload(a.pdf, day, name=f"{a.date} LinkedIn carousel.pdf", mime="application/pdf")
        print("pdf:", p["webViewLink"])


if __name__ == "__main__":
    main()
