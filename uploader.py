import os
import re
import json
import time
import random
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import httplib2
import google_auth_httplib2

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError


# ============================================================
# CONFIGURATION
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]

DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "").strip()
TOKEN_FILE = "token.json"
HISTORY_FILE = "upload_history.json"

MAX_UPLOADS_PER_RUN = int(os.getenv("MAX_UPLOADS_PER_RUN", "1"))
MAX_SHORT_DURATION = 180

CHUNK_SIZE = 8 * 1024 * 1024

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm",
    ".wmv", ".flv", ".3gp", ".3g2", ".mpeg", ".mpg",
    ".mpe", ".mpv", ".m2v", ".mts", ".m2ts", ".ts",
    ".vob", ".ogv", ".divx", ".f4v", ".asf", ".mxf",
}


# ============================================================
# TITLE AND DESCRIPTION GENERATION
# ============================================================

TITLE_HOOKS = [
    "You Won't Believe This",
    "The Truth Is Surprising",
    "Most People Don't Know This",
    "This Is Actually Real",
    "Here's Something Interesting",
    "The Hidden Truth",
    "This Will Blow Your Mind",
    "Wait Until You See This",
    "An Incredible Fact",
    "The World Is Full of Surprises",
    "This Is More Interesting Than You Think",
    "A Fact Worth Knowing",
]

TITLE_TEMPLATES = [
    "{hook}!",
    "{hook} 🤯",
    "{hook} | Amazing Facts",
    "{hook} | Did You Know?",
    "{hook} | Interesting Facts",
    "{hook} | Facts You Should Know",
    "{hook} | Mind Blowing Facts",
    "{hook} | Knowledge Shorts",
    "{hook} | Unbelievable Facts",
    "{hook} | Fact of the Day",
    "{hook} | Learn Something New",
    "{hook} | What Happens?",
]

CHANNEL_DESCRIPTION = (
    "Discover fascinating facts, surprising knowledge, and interesting "
    "things about the world. Subscribe to WhatHappensFactora for more "
    "informative videos and Shorts!\n\n"
    "#Shorts #Facts #Knowledge #DidYouKnow"
)

BASE_TAGS = [
    "facts",
    "interesting facts",
    "amazing facts",
    "did you know",
    "knowledge",
    "educational shorts",
    "youtube shorts",
    "shorts",
    "WhatHappensFactora",
]


def generate_metadata(file_id, filename):
    """
    Generates a title without exposing the original Drive filename.
    Tags may use meaningful words from the filename.
    """

    seed = sum(ord(char) for char in file_id)
    rng = random.Random(seed)

    hook = rng.choice(TITLE_HOOKS)
    template = rng.choice(TITLE_TEMPLATES)

    title = template.format(hook=hook)

    # Keep title within YouTube's title limit.
    title = title[:100].strip()

    # Extract useful words from filename for tags only.
    stem = Path(filename).stem.lower()
    words = re.findall(r"[a-z]{3,}", stem)

    filename_tags = []
    for word in words:
        if word not in filename_tags:
            filename_tags.append(word)

    tags = list(dict.fromkeys(BASE_TAGS + filename_tags))
    tags = tags[:30]

    return title, CHANNEL_DESCRIPTION, tags


# ============================================================
# OAUTH AUTHENTICATION
# ============================================================

def get_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(
            "token.json not found. Check the YOUTUBE_TOKEN_JSON GitHub secret."
        )

    credentials = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        print("Refreshing Google OAuth token...")
        credentials.refresh(Request())

        with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(credentials.to_json())

    if not credentials.valid:
        raise RuntimeError(
            "Google OAuth credentials are invalid. "
            "Regenerate token.json with Drive read and YouTube upload scopes."
        )

    return credentials


# ============================================================
# GOOGLE API CLIENTS
# ============================================================

def create_drive_service(credentials):
    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def create_youtube_service(credentials):
    # Avoid following HTTP 308 resumable-upload responses as redirects.
    http = httplib2.Http(timeout=120)
    http.follow_redirects = False

    authorized_http = google_auth_httplib2.AuthorizedHttp(
        credentials,
        http=http,
    )

    return build(
        "youtube",
        "v3",
        http=authorized_http,
        cache_discovery=False,
    )


# ============================================================
# UPLOAD HISTORY / DUPLICATE PREVENTION
# ============================================================

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {"uploaded_file_ids": [], "uploaded_files": []}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as history_file:
            data = json.load(history_file)
    except (json.JSONDecodeError, OSError):
        print("WARNING: History file could not be read. Starting empty history.")
        return {"uploaded_file_ids": [], "uploaded_files": []}

    if isinstance(data, list):
        ids = []
        for item in data:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict) and item.get("file_id"):
                ids.append(item["file_id"])

        return {
            "uploaded_file_ids": list(dict.fromkeys(ids)),
            "uploaded_files": [],
        }

    if not isinstance(data, dict):
        return {"uploaded_file_ids": [], "uploaded_files": []}

    ids = data.get("uploaded_file_ids", [])
    if not isinstance(ids, list):
        ids = []

    # Support older history formats too.
    for key in ("uploaded_ids", "uploaded_files"):
        old_items = data.get(key, [])

        if isinstance(old_items, list):
            for item in old_items:
                if isinstance(item, str):
                    ids.append(item)
                elif isinstance(item, dict):
                    old_id = item.get("file_id") or item.get("id")
                    if old_id:
                        ids.append(old_id)

    data["uploaded_file_ids"] = list(dict.fromkeys(ids))

    if not isinstance(data.get("uploaded_files"), list):
        data["uploaded_files"] = []

    return data


def save_history(history):
    history["last_updated"] = datetime.now(
        timezone.utc
    ).isoformat()

    with open(HISTORY_FILE, "w", encoding="utf-8") as history_file:
        json.dump(history, history_file, indent=2, ensure_ascii=False)

    print("Upload history saved.")


def mark_as_uploaded(history, file_id, filename, video_id):
    if file_id not in history["uploaded_file_ids"]:
        history["uploaded_file_ids"].append(file_id)

    history["uploaded_files"].append({
        "file_id": file_id,
        "filename": filename,
        "youtube_video_id": video_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })

    save_history(history)


# ============================================================
# GOOGLE DRIVE VIDEO DISCOVERY
# ============================================================

def list_drive_videos(drive_service):
    print("Fetching videos from Google Drive...")

    videos = []
    page_token = None

    while True:
        response = drive_service.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed = false",
            pageSize=1000,
            pageToken=page_token,
            orderBy="createdTime",
            fields=(
                "nextPageToken,"
                "files(id,name,mimeType,size,createdTime)"
            ),
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        for item in response.get("files", []):
            filename = item.get("name", "")
            mime_type = item.get("mimeType", "")

            is_video = (
                mime_type.startswith("video/")
                or Path(filename).suffix.lower() in VIDEO_EXTENSIONS
            )

            if is_video:
                videos.append(item)

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    print(f"Total videos in Drive: {len(videos)}")
    return videos


# ============================================================
# DOWNLOAD VIDEO FROM DRIVE
# ============================================================

def download_video(drive_service, file_id, filename):
    suffix = Path(filename).suffix.lower() or ".mp4"

    temporary_file = tempfile.NamedTemporaryFile(
        prefix="whf_",
        suffix=suffix,
        delete=False,
    )

    filepath = temporary_file.name
    temporary_file.close()

    print(f"Downloading: {filename}")

    request = drive_service.files().get_media(fileId=file_id)

    with open(filepath, "wb") as output_file:
        downloader = MediaIoBaseDownload(
            output_file,
            request,
            chunksize=8 * 1024 * 1024,
        )

        done = False

        while not done:
            status, done = downloader.next_chunk()

            if status:
                print(
                    f"Download progress: "
                    f"{int(status.progress() * 100)}%"
                )

    print("Download completed.")
    return filepath


# ============================================================
# SHORTS VALIDATION USING FFPROBE
# ============================================================

def validate_short(filepath):
    """
    Accepts portrait or square videos up to 180 seconds.
    Uses FFprobe to read duration and video dimensions.
    """

    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
        "-show_entries",
        "format=duration",
        "-of", "json",
        filepath,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe not found. Install FFmpeg and ensure ffprobe is in PATH."
        )
    except subprocess.CalledProcessError as error:
        print("FFprobe error:", error.stderr)
        return False, "Could not read video information"

    try:
        info = json.loads(result.stdout)

        duration = float(info.get("format", {}).get("duration", 0))

        streams = info.get("streams", [])
        if not streams:
            return False, "No video stream found"

        stream = streams[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))

        # Correct dimensions for rotated videos.
        rotation = 0

        for side_data in stream.get("side_data_list", []):
            if "rotation" in side_data:
                rotation = int(float(side_data["rotation"]))
                break

        if not rotation:
            rotation = int(float(
                stream.get("tags", {}).get("rotate", 0)
            ))

        if abs(rotation) in (90, 270):
            width, height = height, width

    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False, "Invalid video metadata"

    print(
        f"Video details: {width}x{height}, "
        f"{duration:.2f} seconds"
    )

    if duration <= 0:
        return False, "Invalid video duration"

    if duration > MAX_SHORT_DURATION:
        return False, f"Longer than {MAX_SHORT_DURATION} seconds"

    if width <= 0 or height <= 0:
        return False, "Invalid video dimensions"

    if width > height:
        return False, "Horizontal video; Shorts validation failed"

    return True, "Eligible for Shorts upload"


# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def upload_to_youtube(youtube_service, filepath, title, description, tags):
    print("Starting YouTube upload...")
    print("Title:", title)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        filepath,
        chunksize=CHUNK_SIZE,
        resumable=True,
    )

    request = youtube_service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    retry_count = 0
    max_retries = 8

    while response is None:
        try:
            status, response = request.next_chunk()

            if status:
                print(
                    f"YouTube upload progress: "
                    f"{int(status.progress() * 100)}%"
                )

            retry_count = 0

        except HttpError as error:
            # Do not retry permanent client-side errors.
            if error.resp.status < 500 and error.resp.status != 429:
                raise

            retry_count += 1

            if retry_count > max_retries:
                raise

            wait_time = min(2 ** retry_count, 60)
            print(
                f"YouTube API error {error.resp.status}. "
                f"Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)

        except (httplib2.HttpLib2Error, OSError) as error:
            retry_count += 1

            if retry_count > max_retries:
                raise

            wait_time = min(2 ** retry_count, 60)
            print(
                f"Network error: {error}. "
                f"Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)

    video_id = response.get("id")

    if not video_id:
        raise RuntimeError("YouTube did not return a video ID.")

    print("Upload successful!")
    print(f"YouTube video ID: {video_id}")
    print(f"Video URL: https://www.youtube.com/watch?v={video_id}")

    return video_id


# ============================================================
# MAIN AUTOMATION
# ============================================================

def main():
    if not DRIVE_FOLDER_ID:
        raise RuntimeError("DRIVE_FOLDER_ID environment variable is missing.")

    if MAX_UPLOADS_PER_RUN < 1:
        raise ValueError("MAX_UPLOADS_PER_RUN must be at least 1.")

    print("=" * 55)
    print("WHAT HAPPENS FACTORA - YOUTUBE AUTOMATION")
    print("=" * 55)

    credentials = get_credentials()

    drive_service = create_drive_service(credentials)
    youtube_service = create_youtube_service(credentials)

    history = load_history()
    uploaded_ids = set(history["uploaded_file_ids"])

    videos = list_drive_videos(drive_service)

    pending_videos = [
        video for video in videos
        if video["id"] not in uploaded_ids
    ]

    print(f"Already uploaded: {len(uploaded_ids)}")
    print(f"Pending videos: {len(pending_videos)}")
    print(f"Maximum uploads this run: {MAX_UPLOADS_PER_RUN}")

    if not pending_videos:
        print("No pending videos found.")
        return

    successful_uploads = 0

    for video in pending_videos:
        if successful_uploads >= MAX_UPLOADS_PER_RUN:
            break

        file_id = video["id"]
        filename = video["name"]
        filepath = None

        print("\n" + "-" * 55)
        print("Checking next video:", filename)

        try:
            filepath = download_video(
                drive_service,
                file_id,
                filename,
            )

            eligible, reason = validate_short(filepath)

            if not eligible:
                print("SKIPPED:", reason)
                continue

            print("Shorts validation passed.")

            title, description, tags = generate_metadata(
                file_id,
                filename,
            )

            video_id = upload_to_youtube(
                youtube_service,
                filepath,
                title,
                description,
                tags,
            )

            # Save history only after a successful YouTube upload.
            mark_as_uploaded(
                history,
                file_id,
                filename,
                video_id,
            )

            successful_uploads += 1

        except Exception as error:
            print(f"ERROR processing {filename}: {error}")
            raise

        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass

    print("\n" + "=" * 55)
    print("RUN COMPLETED")
    print(f"Successful uploads this run: {successful_uploads}")
    print("=" * 55)


if __name__ == "__main__":
    main()
