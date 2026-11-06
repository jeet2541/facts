import json
import os
import re
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import httplib2
from google_auth_httplib2 import AuthorizedHttp

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
TOKEN_PATH = ROOT / "token.json"
HISTORY_PATH = ROOT / "upload_history.json"
DOWNLOAD_DIR = ROOT / "downloads"

VIDEO_MIME_PREFIX = "video/"

def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def safe_title(filename, max_len=100):
    stem = Path(filename).stem
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem[:max_len].strip() or "Interesting Facts"

def build_clients():
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            "token.json is missing. Run auth.py locally, then add its full contents "
            "as the GitHub secret YOUTUBE_TOKEN_JSON."
        )
    token_data = load_json(TOKEN_PATH, {})
    creds = Credentials.from_authorized_user_info(token_data)
    if not creds.valid and not creds.refresh_token:
        raise RuntimeError("OAuth token is invalid and has no refresh token. Re-run auth.py.")
    authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=120))
    drive = build("drive", "v3", http=authed_http, cache_discovery=False)
    youtube = build("youtube", "v3", http=authed_http, cache_discovery=False)
    return drive, youtube

def list_drive_videos(drive, folder_id):
    query = f"'{folder_id}' in parents and trashed = false"
    response = drive.files().list(
        q=query,
        pageSize=100,
        orderBy="createdTime asc",
        fields="files(id,name,mimeType,size,createdTime)"
    ).execute()
    # Drive query syntax does not reliably support MIME-type prefix matching;
    # filter the returned metadata locally instead.
    return [
        item for item in response.get("files", [])
        if item.get("mimeType", "").startswith(VIDEO_MIME_PREFIX)
    ]

def download_drive_file(drive, file_id, destination):
    request = drive.files().get_media(fileId=file_id)
    with io.FileIO(destination, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download: {int(status.progress() * 100)}%")

def upload_video(youtube, filepath, title, description, tags, category_id, privacy):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": str(category_id)
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }
    media = MediaFileUpload(
        str(filepath),
        mimetype="video/*",
        chunksize=8 * 1024 * 1024,
        resumable=True
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload: {int(status.progress() * 100)}%")
    return response["id"]

def main():
    config = load_json(CONFIG_PATH, {})
    history = load_json(HISTORY_PATH, {"uploaded_file_ids": [], "uploads": []})
    folder_id = os.getenv("DRIVE_FOLDER_ID") or config.get("drive_folder_id", "").strip()
    if not folder_id or "PASTE_" in folder_id:
        raise ValueError("Set drive_folder_id in config.json or the DRIVE_FOLDER_ID environment variable.")

    max_uploads = int(os.getenv("MAX_UPLOADS_PER_RUN", config.get("max_uploads_per_run", 1)))
    privacy = os.getenv("YOUTUBE_PRIVACY_STATUS", config.get("privacy_status", "public"))
    if privacy not in {"public", "unlisted", "private"}:
        raise ValueError("privacy_status must be public, unlisted, or private.")

    description = config.get("description", "Learn something new with WhatHappensFactora. Subscribe for more facts and educational videos.")
    tags = config.get("tags", ["facts", "education", "knowledge", "learning", "interesting facts"])
    category_id = config.get("category_id", "27")  # Education
    history.setdefault("uploaded_file_ids", [])
    history.setdefault("uploads", [])

    drive, youtube = build_clients()
    videos = list_drive_videos(drive, folder_id)
    pending = [v for v in videos if v["id"] not in set(history["uploaded_file_ids"])]

    if not pending:
        print("No new videos found in the Drive folder.")
        return

    DOWNLOAD_DIR.mkdir(exist_ok=True)
    completed = 0
    for item in pending:
        if completed >= max_uploads:
            break
        name = item.get("name", "video.mp4")
        destination = DOWNLOAD_DIR / name
        print(f"Processing: {name} ({item['id']})")
        download_drive_file(drive, item["id"], destination)
        title = safe_title(name)
        video_id = upload_video(
            youtube=youtube,
            filepath=destination,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            privacy=privacy
        )
        history["uploaded_file_ids"].append(item["id"])
        history["uploads"].append({
            "drive_file_id": item["id"],
            "filename": name,
            "youtube_video_id": video_id,
            "title": title
        })
        save_json(HISTORY_PATH, history)
        destination.unlink(missing_ok=True)
        completed += 1
        print(f"SUCCESS: https://www.youtube.com/watch?v={video_id}")

    print(f"Finished. Uploaded {completed} video(s).")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
