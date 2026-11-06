
import json
import os
import re
import sys
import io
import mimetypes
import hashlib
import subprocess
from pathlib import Path

import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_httplib2 import AuthorizedHttp


# ==================================================
# CONFIGURATION
# ==================================================

ROOT = Path(__file__).resolve().parent

CONFIG_PATH = ROOT / "config.json"
TOKEN_PATH = ROOT / "token.json"
HISTORY_PATH = ROOT / "upload_history.json"
DOWNLOAD_DIR = ROOT / "downloads"

VIDEO_MIME_PREFIX = "video/"
CHANNEL_NAME = "WhatHappensFactora"

MAX_SHORT_DURATION = 180
SHORTS_HASHTAG = "#Shorts"


# ==================================================
# 1. TITLE GENERATOR
# 12 HOOKS x 12 FORMATS = 144 UNIQUE TITLES
# Original Drive filename is NEVER used in title.
# ==================================================

TITLE_HOOKS = [
    "Amazing",
    "Mind-Blowing",
    "Unbelievable",
    "Incredible",
    "Shocking",
    "Fascinating",
    "Surprising",
    "Unknown",
    "Extraordinary",
    "Crazy",
    "Interesting",
    "Unexplained"
]

TITLE_FORMATS = [
    "{hook} Facts You Should Know",
    "{hook} Things That Will Blow Your Mind",
    "{hook} Truths You Never Knew",
    "{hook} Facts That Sound Impossible",
    "{hook} Things Most People Don't Know",
    "{hook} Discoveries You Need to See",
    "{hook} Facts About Our World",
    "{hook} Knowledge That Will Amaze You",
    "{hook} Facts You Won't Believe",
    "{hook} Things You Never Expected",
    "{hook} Facts Worth Knowing Today",
    "{hook} Discoveries That Will Surprise You"
]


# ==================================================
# 2. DESCRIPTION GENERATOR
# ==================================================

DESCRIPTIONS = [
    """Discover something new today!

Explore fascinating information and surprising facts with WhatHappensFactora.

Subscribe for more amazing facts, science, technology and knowledge.

#Facts #DidYouKnow #Knowledge #Shorts""",

    """Your daily dose of knowledge is here!

Learn something interesting and discover information you may not have known before.

Subscribe to WhatHappensFactora for more educational videos.

#AmazingFacts #InterestingFacts #Education #Shorts""",

    """The world is full of amazing discoveries!

Watch, explore and expand your knowledge with WhatHappensFactora.

Stay curious and subscribe for more!

#Facts #Learning #Discovery #Shorts""",

    """Ready to learn something new?

Explore interesting information and fascinating facts with WhatHappensFactora.

Subscribe and never stop learning!

#Knowledge #DidYouKnow #FactsDaily #Shorts""",

    """Curiosity makes learning exciting!

Discover amazing information and explore the world around you.

Subscribe to WhatHappensFactora for more interesting content.

#Curiosity #Education #InterestingFacts #Shorts""",

    """There is always something new to discover!

Enjoy fascinating facts, informative videos and interesting knowledge.

Subscribe to WhatHappensFactora.

#AmazingFacts #Knowledge #Learning #Shorts""",

    """Think you know everything?

Explore something new with WhatHappensFactora and discover facts that make you think.

Subscribe for more!

#MindBlowingFacts #Facts #Shorts""",

    """Welcome to WhatHappensFactora!

Explore facts, science, technology, mysteries and educational content.

Stay curious and subscribe for more discoveries.

#WhatHappensFactora #Facts #Education #Shorts""",

    """Learning something new every day makes a difference!

Watch, explore and discover interesting information with us.

Subscribe to WhatHappensFactora.

#DailyFacts #Knowledge #DidYouKnow #Shorts""",

    """Amazing things happen all around us!

Discover interesting information and fascinating facts in this video.

Follow WhatHappensFactora for more discoveries.

#InterestingFacts #Discover #Shorts""",

    """Knowledge begins with curiosity!

Explore the unknown and discover interesting facts with WhatHappensFactora.

Subscribe for more informative videos.

#Learning #Facts #Knowledge #Shorts""",

    """Never stop asking questions!

Discover fascinating information and explore the world through facts.

Subscribe to WhatHappensFactora for more.

#Facts #Curiosity #Education #Shorts"""
]


# ==================================================
# 3. CHANNEL TAGS
# ==================================================

CHANNEL_TAGS = [
    "WhatHappensFactora",
    "facts",
    "amazing facts",
    "interesting facts",
    "did you know",
    "knowledge",
    "education",
    "learning",
    "informative videos",
    "daily facts",
    "explained",
    "shorts",
    "YouTube Shorts"
]


# ==================================================
# 4. TOPIC-BASED TAGS
# ==================================================

TOPIC_TAGS = {
    "science": [
        "science facts",
        "scientific discoveries",
        "science explained",
        "experiments"
    ],
    "space": [
        "space facts",
        "universe",
        "astronomy",
        "planets",
        "NASA"
    ],
    "technology": [
        "technology facts",
        "tech explained",
        "future technology",
        "innovation"
    ],
    "artificial intelligence": [
        "AI facts",
        "artificial intelligence",
        "machine learning",
        "future of AI"
    ],
    "history": [
        "history facts",
        "historical facts",
        "ancient history"
    ],
    "human": [
        "human body facts",
        "human brain",
        "biology",
        "body facts"
    ],
    "animal": [
        "animal facts",
        "wildlife",
        "nature facts"
    ],
    "ocean": [
        "ocean facts",
        "marine life",
        "sea creatures"
    ],
    "mystery": [
        "mystery facts",
        "unsolved mysteries",
        "strange facts"
    ],
    "world": [
        "world facts",
        "geography",
        "countries",
        "places"
    ]
}


# ==================================================
# 5. JSON HELPERS
# ==================================================

def load_json(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


# ==================================================
# 6. SHORTS VIDEO VALIDATION
# Requires FFmpeg / ffprobe.
# Accepts vertical and square videos up to 180 seconds.
# ==================================================

def validate_short(filepath):
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height:stream_side_data=rotation",
        "-of", "json",
        str(filepath)
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=60
        )

    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe not found. Install FFmpeg before running uploader.py."
        )

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Could not inspect video: {exc.stderr}"
        )

    data = json.loads(result.stdout)

    duration = float(
        data.get("format", {}).get("duration", 0)
    )

    video_stream = next(
        (
            stream for stream in data.get("streams", [])
            if stream.get("codec_type") == "video"
        ),
        None
    )

    if not video_stream:
        return False, "No video stream found."

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    # Handle videos recorded with rotation metadata.
    rotation = 0

    for side_data in video_stream.get("side_data_list", []):
        if "rotation" in side_data:
            rotation = int(float(side_data["rotation"]))
            break

    if abs(rotation) % 180 == 90:
        width, height = height, width

    print(
        f"Video details: {width}x{height}, "
        f"{duration:.2f} seconds"
    )

    if duration <= 0:
        return False, "Invalid or unreadable video duration."

    if duration > MAX_SHORT_DURATION:
        return False, (
            f"Duration is {duration:.1f}s. "
            "Maximum Shorts duration is 180 seconds."
        )

    if width <= 0 or height <= 0:
        return False, "Invalid video dimensions."

    if width > height:
        return False, (
            f"Horizontal video ({width}x{height}). "
            "Only vertical or square videos are accepted."
        )

    return True, "Eligible for YouTube Shorts."


# ==================================================
# 7. TOPIC DETECTION
# Used for tags only, NOT for title.
# ==================================================

def extract_topic(filename):
    stem = Path(filename).stem

    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"^\d+[\s.]*", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    words = [
        word for word in stem.split()
        if not word.isdigit() and not re.search(r"\d{4,}", word)
    ]

    topic = " ".join(words).strip()

    if not topic:
        return "general facts"

    return topic[:70]


# ==================================================
# 8. DETECT TOPIC TAGS
# ==================================================

def detect_topic_tags(topic):
    text = topic.lower()
    result = []

    for keyword, tags in TOPIC_TAGS.items():
        if keyword in text:
            result.extend(tags)

    return result


# ==================================================
# 9. UNIQUE TITLE GENERATOR
# ==================================================

def generate_title(history):
    used_titles = {
        item.get("title", "").lower()
        for item in history.get("uploads", [])
    }

    total = len(TITLE_HOOKS) * len(TITLE_FORMATS)
    start = len(history.get("uploads", [])) % total

    for offset in range(total):
        index = (start + offset) % total

        hook = TITLE_HOOKS[index % len(TITLE_HOOKS)]

        template = TITLE_FORMATS[
            (index // len(TITLE_HOOKS)) % len(TITLE_FORMATS)
        ]

        title = template.format(hook=hook)

        if SHORTS_HASHTAG.lower() not in title.lower():
            title = f"{title} {SHORTS_HASHTAG}"

        if title.lower() not in used_titles:
            return title[:100]

    suffix = hashlib.sha256(
        str(len(history.get("uploads", []))).encode()
    ).hexdigest()[:6]

    return f"Discover More Amazing Facts #{suffix} {SHORTS_HASHTAG}"[:100]


# ==================================================
# 10. DESCRIPTION GENERATOR
# ==================================================

def generate_description(history):
    index = len(history.get("uploads", [])) % len(DESCRIPTIONS)

    description = DESCRIPTIONS[index].strip()

    if SHORTS_HASHTAG.lower() not in description.lower():
        description += "\n\n#Shorts"

    return description[:5000]


# ==================================================
# 11. AUTOMATIC TAG GENERATOR
# ==================================================

def generate_tags(topic, config):
    tags = []

    tags.extend(config.get("tags", []))
    tags.extend(CHANNEL_TAGS)
    tags.extend(detect_topic_tags(topic))

    topic_words = topic.split()

    if len(topic_words) >= 2:
        for word in topic_words:
            clean_word = re.sub(r"[^a-zA-Z]", "", word)

            if len(clean_word) > 3:
                tags.append(clean_word.lower())

    unique_tags = []
    seen = set()

    for tag in tags:
        tag = str(tag).strip()

        if not tag:
            continue

        key = tag.lower()

        if key not in seen:
            seen.add(key)
            unique_tags.append(tag)

    final_tags = []
    total_length = 0

    for tag in unique_tags:
        extra_length = len(tag) + (1 if final_tags else 0)

        if total_length + extra_length > 500:
            break

        final_tags.append(tag)
        total_length += extra_length

    return final_tags


# ==================================================
# 12. GOOGLE API CLIENTS
# ==================================================

def build_clients():
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            "token.json missing. Run auth.py and configure "
            "GitHub secret YOUTUBE_TOKEN_JSON."
        )

    token_data = load_json(TOKEN_PATH, {})

    creds = Credentials.from_authorized_user_info(token_data)

    if not creds.valid and not creds.refresh_token:
        raise RuntimeError(
            "OAuth token invalid. Re-run auth.py."
        )

    http = httplib2.Http(timeout=120)
    http.follow_redirects = False

    authed_http = AuthorizedHttp(
        creds,
        http=http
    )

    drive = build(
        "drive",
        "v3",
        http=authed_http,
        cache_discovery=False
    )

    youtube = build(
        "youtube",
        "v3",
        http=authed_http,
        cache_discovery=False
    )

    return drive, youtube


# ==================================================
# 13. GOOGLE DRIVE VIDEO LIST
# ==================================================

def list_drive_videos(drive, folder_id):
    videos = []
    page_token = None

    while True:
        response = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            pageSize=100,
            orderBy="createdTime asc",
            pageToken=page_token,
            fields=(
                "nextPageToken,"
                "files(id,name,mimeType,size,createdTime)"
            )
        ).execute()

        for item in response.get("files", []):
            if item.get("mimeType", "").startswith(VIDEO_MIME_PREFIX):
                videos.append(item)

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return videos


# ==================================================
# 14. DOWNLOAD VIDEO
# ==================================================

def download_drive_file(drive, file_id, destination):
    request = drive.files().get_media(
        fileId=file_id
    )

    with io.FileIO(destination, "wb") as file:
        downloader = MediaIoBaseDownload(
            file,
            request,
            chunksize=8 * 1024 * 1024
        )

        done = False

        while not done:
            status, done = downloader.next_chunk(
                num_retries=5
            )

            if status:
                print(
                    f"Download: {int(status.progress() * 100)}%"
                )


# ==================================================
# 15. YOUTUBE PUBLIC SHORTS UPLOAD
# ==================================================

def upload_video(
    youtube,
    filepath,
    title,
    description,
    tags,
    category_id
):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": str(category_id)
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    mime_type, _ = mimetypes.guess_type(str(filepath))

    if not mime_type or not mime_type.startswith("video/"):
        mime_type = "video/mp4"

    media = MediaFileUpload(
        str(filepath),
        mimetype=mime_type,
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
        status, response = request.next_chunk(
            num_retries=5
        )

        if status:
            print(
                f"Upload: {int(status.progress() * 100)}%"
            )

    return response["id"]


# ==================================================
# 16. MAIN AUTOMATION
# ==================================================

def main():
    config = load_json(
        CONFIG_PATH,
        {}
    )

    history = load_json(
        HISTORY_PATH,
        {
            "uploaded_file_ids": [],
            "uploads": []
        }
    )

    folder_id = (
        os.getenv("DRIVE_FOLDER_ID")
        or config.get("drive_folder_id", "").strip()
    )

    if not folder_id or "PASTE_" in folder_id:
        raise ValueError(
            "Set DRIVE_FOLDER_ID in GitHub Secrets or config.json."
        )

    max_uploads = int(
        os.getenv(
            "MAX_UPLOADS_PER_RUN",
            config.get("max_uploads_per_run", 1)
        )
    )

    if max_uploads < 1:
        raise ValueError(
            "MAX_UPLOADS_PER_RUN must be at least 1."
        )

    category_id = config.get("category_id", "27")

    history.setdefault("uploaded_file_ids", [])
    history.setdefault("uploads", [])

    print("Connecting to Google APIs...")

    drive, youtube = build_clients()

    print("Connected successfully.")
    print("Checking Google Drive folder...")

    videos = list_drive_videos(
        drive,
        folder_id
    )

    uploaded_ids = set(
        history["uploaded_file_ids"]
    )

    pending = [
        video for video in videos
        if video["id"] not in uploaded_ids
    ]

    print(f"Total videos in Drive: {len(videos)}")
    print(f"Already uploaded: {len(uploaded_ids)}")
    print(f"Pending videos: {len(pending)}")

    if not pending:
        print("No new videos found in the Drive folder.")
        return

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    completed = 0
    skipped = 0

    for item in pending:

        if completed >= max_uploads:
            break

        file_id = item["id"]
        original_name = item.get("name", "video.mp4")

        safe_filename = Path(original_name).name
        destination = DOWNLOAD_DIR / safe_filename

        print("\n================================")
        print(f"Processing Drive file: {original_name}")
        print("================================")

        try:
            # Download
            download_drive_file(
                drive,
                file_id,
                destination
            )

            # Validate Shorts eligibility
            eligible, reason = validate_short(destination)

            if not eligible:
                print(f"SKIPPED: {reason}")
                skipped += 1
                continue

            print(f"SHORTS CHECK PASSED: {reason}")

            # Generate metadata
            topic = extract_topic(original_name)

            title = generate_title(history)
            description = generate_description(history)

            tags = generate_tags(
                topic,
                config
            )

            print(f"Detected topic for tags: {topic}")
            print(f"Generated title: {title}")
            print(f"Tags: {', '.join(tags)}")
            print("Format: YOUTUBE SHORTS")
            print("Privacy: PUBLIC")

            # Upload
            video_id = upload_video(
                youtube=youtube,
                filepath=destination,
                title=title,
                description=description,
                tags=tags,
                category_id=category_id
            )

            # Save history only after successful upload
            history["uploaded_file_ids"].append(file_id)

            history["uploads"].append({
                "drive_file_id": file_id,
                "filename": original_name,
                "youtube_video_id": video_id,
                "title": title,
                "description": description,
                "tags": tags,
                "privacy": "public",
                "format": "shorts"
            })

            save_json(
                HISTORY_PATH,
                history
            )

            completed += 1

            print("\nSHORT UPLOAD SUCCESSFUL")
            print(
                f"https://www.youtube.com/shorts/{video_id}"
            )

        finally:
            if destination.exists():
                destination.unlink()

    print("\n================================")
    print(f"Uploaded Shorts: {completed}")
    print(f"Skipped ineligible videos: {skipped}")
    print("Privacy: PUBLIC")
    print("Upload history saved.")
    print("================================")


# ==================================================
# 17. RUN
# ==================================================

if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr
        )
        raise
