
import json
import os
import re
import sys
import io
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

# --------------------------------------------------
# 1. TITLE GENERATOR: 12 HOOKS x 12 FORMATS = 144+
# --------------------------------------------------

TITLE_HOOKS = [
    "Amazing",
    "Mind-Blowing",
    "Unbelievable",
    "Shocking",
    "Incredible",
    "Unknown",
    "Fascinating",
    "Surprising",
    "Crazy",
    "Interesting",
    "Hidden",
    "Extraordinary"
]

TITLE_FORMATS = [
    "{hook} Facts About {topic}",
    "What Happens When {topic}?",
    "The Truth About {topic}",
    "Things You Didn't Know About {topic}",
    "Why Does {topic} Matter?",
    "{topic}: Explained Simply",
    "The Science Behind {topic}",
    "What Nobody Tells You About {topic}",
    "Discover the Secrets of {topic}",
    "How Does {topic} Actually Work?",
    "The Hidden Side of {topic}",
    "You Won't Believe These Facts About {topic}"
]

# --------------------------------------------------
# 2. DESCRIPTION ROTATION
# --------------------------------------------------

DESCRIPTIONS = [
    """Discover something new about {topic}!

In this video, we explore fascinating facts and information about {topic} that you may not have known before.

Subscribe to WhatHappensFactora for more interesting facts, science, technology and knowledge.

#Facts #DidYouKnow #Knowledge #Shorts""",

    """How much do you really know about {topic}?

Watch till the end to discover interesting information and surprising facts.

Follow WhatHappensFactora for more educational and informative videos.

#AmazingFacts #InterestingFacts #Education #Shorts""",

    """Explore the world of {topic} with WhatHappensFactora!

Learn something new through simple explanations, fascinating facts and useful knowledge.

Subscribe for more daily discoveries.

#Facts #Learning #ScienceFacts #Shorts""",

    """There is always something interesting to learn about {topic}!

This video brings you useful information and facts in a simple and engaging way.

Subscribe to WhatHappensFactora for more discoveries.

#Knowledge #FactsDaily #DidYouKnow #Shorts""",

    """Let's understand {topic}!

Discover the facts, explanations and interesting details behind this subject.

Like, share and subscribe to WhatHappensFactora for more content.

#InterestingFacts #Explained #LearnSomethingNew #Shorts""",

    """Ready to learn something new?

Today's topic is {topic}. Discover fascinating details and expand your knowledge with WhatHappensFactora.

Subscribe for more videos!

#AmazingFacts #Knowledge #Education #Shorts""",

    """What makes {topic} so interesting?

Watch this video to explore facts and information that make you think differently.

More facts and discoveries coming on WhatHappensFactora.

#MindBlowingFacts #Facts #Shorts""",

    """Your daily dose of knowledge is here!

Today's video explores {topic} with interesting information and easy-to-understand explanations.

Subscribe to WhatHappensFactora.

#DailyFacts #Learning #DidYouKnow #Shorts""",

    """Learn more about {topic} in this quick and informative video.

Stay curious, keep exploring and never stop learning.

Follow WhatHappensFactora for more interesting content.

#Education #InterestingFacts #Knowledge #Shorts""",

    """The world is full of amazing things!

Today, we take a closer look at {topic} and explore some interesting details.

Subscribe for more facts and discoveries.

#Discover #Facts #Science #Shorts""",

    """Curiosity starts with a question!

Explore {topic} and discover useful facts and information in this video.

Join WhatHappensFactora for more daily knowledge.

#Curiosity #Facts #Learning #Shorts""",

    """Welcome to WhatHappensFactora!

Today's topic: {topic}

Explore fascinating information, learn new things and discover the world around you.

Subscribe for more informative videos.

#WhatHappensFactora #Facts #Knowledge #Shorts"""
]

# --------------------------------------------------
# 3. CHANNEL TAGS
# --------------------------------------------------

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

# Topic-based keyword groups
TOPIC_TAGS = {
    "science": [
        "science facts", "scientific discoveries",
        "science explained", "experiments"
    ],
    "space": [
        "space facts", "universe", "astronomy",
        "planets", "NASA"
    ],
    "technology": [
        "technology facts", "tech explained",
        "future technology", "innovation"
    ],
    "ai": [
        "AI facts", "artificial intelligence",
        "machine learning", "future of AI"
    ],
    "history": [
        "history facts", "historical facts",
        "ancient history"
    ],
    "human": [
        "human body facts", "human brain",
        "biology", "body facts"
    ],
    "animal": [
        "animal facts", "wildlife",
        "nature facts"
    ],
    "ocean": [
        "ocean facts", "marine life",
        "sea creatures"
    ],
    "mystery": [
        "mystery facts", "unsolved mysteries",
        "strange facts"
    ],
    "world": [
        "world facts", "geography",
        "countries", "places"
    ]
}


# --------------------------------------------------
# JSON HELPERS
# --------------------------------------------------

def load_json(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------
# TOPIC DETECTION
# --------------------------------------------------

def extract_topic(filename):
    stem = Path(filename).stem

    # Replace underscores and hyphens
    stem = re.sub(r"[_-]+", " ", stem)

    # Remove common file numbering
    stem = re.sub(r"^\d+[\s.]*", "", stem)

    # Remove repeated spaces
    stem = re.sub(r"\s+", " ", stem).strip()

    # Ignore filenames containing only numbers
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


# --------------------------------------------------
# UNIQUE TITLE GENERATOR
# --------------------------------------------------

def generate_title(topic, history):
    used_titles = {
        item.get("title", "").lower()
        for item in history.get("uploads", [])
    }

    total_formats = len(TITLE_HOOKS) * len(TITLE_FORMATS)

    # Rotate combinations based on upload history
    start = len(history.get("uploads", [])) % total_formats

    for offset in range(total_formats):
        index = (start + offset) % total_formats

        hook_index = index % len(TITLE_HOOKS)
        format_index = (index // len(TITLE_HOOKS)) % len(TITLE_FORMATS)

        hook = TITLE_HOOKS[hook_index]
        template = TITLE_FORMATS[format_index]

        title = template.format(
            hook=hook,
            topic=topic
        )

        title = re.sub(r"\s+", " ", title).strip()
        title = title[:100].strip()

        if title.lower() not in used_titles:
            return title

    # Fallback if all combinations are used
    return f"{topic} | WhatHappensFactora"[:100]


# --------------------------------------------------
# DESCRIPTION GENERATOR
# --------------------------------------------------

def generate_description(topic, history):
    index = len(history.get("uploads", [])) % len(DESCRIPTIONS)

    description = DESCRIPTIONS[index].format(topic=topic)

    return description[:5000]


# --------------------------------------------------
# TAG GENERATOR
# --------------------------------------------------

def generate_tags(topic, config):
    tags = []

    tags.extend(config.get("tags", []))
    tags.extend(CHANNEL_TAGS)
    tags.extend(detect_topic_tags(topic))

    # Add words from the filename/topic
    words = re.findall(r"[a-zA-Z0-9]+", topic.lower())

    for word in words:
        if len(word) > 2:
            tags.append(word)

    # Remove duplicates
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

    # YouTube's combined tag character limit is 500
    final_tags = []
    total_length = 0

    for tag in unique_tags:
        extra_length = len(tag) + (1 if final_tags else 0)

        if total_length + extra_length > 500:
            break

        final_tags.append(tag)
        total_length += extra_length

    return final_tags


# --------------------------------------------------
# GOOGLE API CLIENTS
# --------------------------------------------------

def build_clients():
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            "token.json is missing. Run auth.py locally and add its full "
            "contents as the GitHub secret YOUTUBE_TOKEN_JSON."
        )

    token_data = load_json(TOKEN_PATH, {})

    creds = Credentials.from_authorized_user_info(token_data)

    if not creds.valid and not creds.refresh_token:
        raise RuntimeError(
            "OAuth token is invalid and has no refresh token. Re-run auth.py."
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


# --------------------------------------------------
# GOOGLE DRIVE VIDEO LIST
# --------------------------------------------------

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


# --------------------------------------------------
# DOWNLOAD VIDEO
# --------------------------------------------------

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
                print(f"Download: {int(status.progress() * 100)}%")


# --------------------------------------------------
# YOUTUBE UPLOAD
# --------------------------------------------------

def upload_video(
    youtube,
    filepath,
    title,
    description,
    tags,
    category_id,
    privacy
):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
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


# --------------------------------------------------
# MAIN AUTOMATION
# --------------------------------------------------

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

    privacy = os.getenv(
        "YOUTUBE_PRIVACY_STATUS",
        config.get("privacy_status", "private")
    ).strip().lower()

    if privacy not in {"public", "unlisted", "private"}:
        raise ValueError(
            "YOUTUBE_PRIVACY_STATUS must be public, unlisted, or private."
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

        # Avoid unsafe filename paths
        safe_filename = Path(name).name
        destination = DOWNLOAD_DIR / safe_filename

        print("\n--------------------------------")
        print(f"Processing: {name}")
        print(f"Drive ID: {item['id']}")
        print("--------------------------------")

        download_drive_file(
            drive,
            item["id"],
            destination
        )

        # Generate metadata
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

        print(f"Topic: {topic}")
        print(f"Title: {title}")
        print(f"Tags: {', '.join(tags)}")

        # Upload
        video_id = upload_video(
            youtube=youtube,
            filepath=destination,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            privacy=privacy
        )

        # Save upload history
        history["uploaded_file_ids"].append(item["id"])

        history["uploads"].append({
            "drive_file_id": item["id"],
            "filename": name,
            "topic": topic,
            "youtube_video_id": video_id,
            "title": title,
            "description": description,
            "tags": tags
        })

        save_json(HISTORY_PATH, history)

        destination.unlink(missing_ok=True)

        completed += 1

        print(
            f"SUCCESS: https://www.youtube.com/watch?v={video_id}"
        )

    print("\n================================")
    print(f"Finished. Uploaded {completed} video(s).")
    print("Metadata history saved successfully.")
    print("================================")


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
