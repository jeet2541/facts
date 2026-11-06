
import json
import os
import re
import sys
import io
import hashlib
from pathlib import Path

import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_httplib2 import AuthorizedHttp


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
TOKEN_PATH = ROOT / "token.json"
HISTORY_PATH = ROOT / "upload_history.json"
DOWNLOAD_DIR = ROOT / "downloads"

VIDEO_MIME_PREFIX = "video/"


# ==================================================
# 1. TITLE GENERATOR: 144+ COMBINATIONS
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
    "Things That Will Blow Your Mind",
    "The Truth You Never Knew",
    "Facts That Sound Impossible",
    "What Most People Don't Know",
    "Discover Something Amazing Today",
    "The World Is More Interesting Than You Think",
    "You Need to Know These Facts",
    "Prepare to Be Surprised",
    "Knowledge That Will Amaze You",
    "The Most Interesting Things Ever",
    "Can You Believe This Is Real?"
]


# ==================================================
# 2. DESCRIPTION GENERATOR
# ==================================================

DESCRIPTIONS = [
    """Discover something new today!

Explore fascinating information and surprising facts in this video.

Subscribe to WhatHappensFactora for more amazing facts, science, technology and knowledge.

#Facts #DidYouKnow #Knowledge #Shorts""",

    """Your daily dose of knowledge is here!

Learn something interesting and discover information you may not have known before.

Subscribe to WhatHappensFactora for more educational videos.

#AmazingFacts #InterestingFacts #Education #Shorts""",

    """The world is full of amazing discoveries!

Watch this video, expand your knowledge and keep your curiosity alive.

Follow WhatHappensFactora for more interesting content.

#Facts #Learning #Discovery #Shorts""",

    """Ready to learn something new?

Explore interesting information and fascinating facts with WhatHappensFactora.

Subscribe and never stop learning!

#Knowledge #DidYouKnow #FactsDaily #Shorts""",

    """Curiosity makes learning exciting!

Discover amazing information and explore the world around you.

Subscribe to WhatHappensFactora for more facts and explanations.

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

Stay curious and subscribe for more daily discoveries.

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
    "ai": [
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
# 4. JSON HELPERS
# ==================================================

def load_json(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==================================================
# 5. TOPIC DETECTION
# ==================================================

def extract_topic(filename):
    stem = Path(filename).stem

    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"^\d+[\s.]*", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    if not stem or not re.search(r"[a-zA-Z]", stem):
        return "Interesting Facts"

    return stem[:70].strip()


def detect_topic_tags(topic):
    text = topic.lower()
    result = []

    for keyword, tags in TOPIC_TAGS.items():
        if keyword in text:
            result.extend(tags)

    return result


# ==================================================
# 6. UNIQUE TITLE GENERATOR
# Original filename is NEVER used in title.
# ==================================================

def generate_title(topic, history):
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

        if title.lower() not in used_titles:
            return title[:100]

    # Fallback: unique deterministic suffix
    suffix = hashlib.sha256(
        str(len(history.get("uploads", []))).encode()
    ).hexdigest()[:6]

    return f"Discover More Amazing Facts #{suffix}"[:100]


# ==================================================
# 7. DESCRIPTION GENERATOR
# ==================================================

def generate_description(topic, history):
    index = len(history.get("uploads", [])) % len(DESCRIPTIONS)

    description = DESCRIPTIONS[index]

    return description[:5000]


# ==================================================
# 8. AUTOMATIC TAG GENERATOR
# ==================================================

def generate_tags(topic, config):
    tags = []

    tags.extend(config.get("tags", []))
    tags.extend(CHANNEL_TAGS)
    tags.extend(detect_topic_tags(topic))

    words = re.findall(r"[a-zA-Z0-9]+", topic.lower())

    for word in words:
        if len(word) > 2:
            tags.append(word)

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
        extra = len(tag) + (1 if final_tags else 0)

        if total_length + extra > 500:
            break

        final_tags.append(tag)
        total_length += extra

    return final_tags


# ==================================================
# 9. GOOGLE API CLIENTS
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

    authed_http = AuthorizedHttp(
        creds,
        http=httplib2.Http(timeout=120)
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
# 10. GOOGLE DRIVE VIDEO LIST
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
            fields="nextPageToken,files(id,name,mimeType,size,createdTime)"
        ).execute()

        for item in response.get("files", []):
            if item.get("mimeType", "").startswith(VIDEO_MIME_PREFIX):
                videos.append(item)

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return videos


# ==================================================
# 11. DOWNLOAD VIDEO
# ==================================================

def download_drive_file(drive, file_id, destination):
    request = drive.files().get_media(fileId=file_id)

    with io.FileIO(destination, "wb") as fh:
        downloader = MediaIoBaseDownload(
            fh,
            request,
            chunksize=8 * 1024 * 1024
        )

        done = False

        while not done:
            status, done = downloader.next_chunk()

            if status:
                print(
                    f"Download: {int(status.progress() * 100)}%"
                )


# ==================================================
# 12. YOUTUBE PUBLIC UPLOAD
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
            print(
                f"Upload: {int(status.progress() * 100)}%"
            )

    return response["id"]


# ==================================================
# 13. MAIN AUTOMATION
# ==================================================

def main():
    config = load_json(CONFIG_PATH, {})

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

    category_id = config.get("category_id", "27")

    history.setdefault("uploaded_file_ids", [])
    history.setdefault("uploads", [])

    drive, youtube = build_clients()

    videos = list_drive_videos(drive, folder_id)

    uploaded_ids = set(history["uploaded_file_ids"])

    pending = [
        video for video in videos
        if video["id"] not in uploaded_ids
    ]

    if not pending:
        print("No new videos found in the Drive folder.")
        return

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    completed = 0

    for item in pending:
        if completed >= max_uploads:
            break

        name = item.get("name", "video.mp4")

        safe_filename = Path(name).name
        destination = DOWNLOAD_DIR / safe_filename

        print("\n================================")
        print(f"Processing Drive file: {name}")
        print("================================")

        download_drive_file(
            drive,
            item["id"],
            destination
        )

        topic = extract_topic(name)

        title = generate_title(topic, history)

        description = generate_description(
            topic,
            history
        )

        tags = generate_tags(
            topic,
            config
        )

        print(f"Detected topic: {topic}")
        print(f"Generated title: {title}")
        print(f"Tags: {', '.join(tags)}")
        print("Privacy: PUBLIC")

        video_id = upload_video(
            youtube=youtube,
            filepath=destination,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id
        )

        history["uploaded_file_ids"].append(item["id"])

        history["uploads"].append({
            "drive_file_id": item["id"],
            "filename": name,
            "topic": topic,
            "youtube_video_id": video_id,
            "title": title,
            "description": description,
            "tags": tags,
            "privacy": "public"
        })

        save_json(HISTORY_PATH, history)

        destination.unlink(missing_ok=True)

        completed += 1

        print(
            f"SUCCESS: https://www.youtube.com/watch?v={video_id}"
        )

    print("\n================================")
    print(f"Uploaded: {completed} video(s)")
    print("Privacy: PUBLIC")
    print("History saved.")
    print("================================")


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
