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
# TITLE AND DESCRIPTION GENERATION - JEETSTORYAI
# ============================================================

CHANNEL_NAME = "JeetStoryAI"

# Broad Hindi storytelling hooks. These are intentionally not tied
# to one particular story topic because the Drive filenames may vary.
TITLE_POOL = [
    "आखिर में जो हुआ, किसी ने सोचा भी नहीं था! 😱",
    "इस कहानी का अंत आपको हैरान कर देगा! 🤯",
    "एक ऐसी कहानी जो दिल छू जाएगी ❤️",
    "आखिर सच क्या था? पूरा वीडियो देखिए!",
    "जब किस्मत ने अचानक पलटी मारी! 😲",
    "इस कहानी में छुपा है एक बड़ा ट्विस्ट!",
    "आखिरी पल तक इंतजार करना! 😳",
    "कभी-कभी सच कल्पना से भी अजीब होता है!",
    "एक छोटा सा फैसला और सब कुछ बदल गया!",
    "जो दिखता है, हमेशा वही सच नहीं होता!",
    "इसका अंत बिल्कुल उम्मीद से अलग है! 😮",
    "एक अनोखी कहानी, एक चौंकाने वाला मोड़!",
    "आगे क्या हुआ, देखकर यकीन नहीं होगा!",
    "इस कहानी ने सबको सोचने पर मजबूर कर दिया!",
    "एक पल में बदल गई पूरी कहानी!",
    "धैर्य रखिए, असली ट्विस्ट अंत में है!",
    "कहानी का सबसे बड़ा राज आखिर खुल गया!",
    "ऐसा मोड़ आपने पहले नहीं देखा होगा!",
    "कभी किसी को कम मत समझना!",
    "एक सीख जो जिंदगी भर याद रहेगी!",
    "इस कहानी से आपको भी कुछ सीख मिलेगी!",
    "अंत देखकर आपका दिल खुश हो जाएगा! 😊",
    "एक ऐसा राज जिसने सबको चौंका दिया!",
    "जब सच्चाई सबके सामने आई!",
    "इस कहानी में आगे जो हुआ, कमाल था!",
    "एक अनोखा सफर और यादगार सीख!",
    "क्या आपने ऐसा कभी सोचा था?",
    "यह कहानी अंत तक जरूर देखना!",
    "आखिरकार उसे अपनी गलती समझ आ गई!",
    "एक कहानी, कई भावनाएं और बड़ा ट्विस्ट!",
    "सब कुछ सामान्य था… फिर अचानक ये हुआ!",
    "आखिरी 5 सेकंड मिस मत करना! 😱",
    "इस कहानी का संदेश बहुत खास है!",
    "एक छोटी सी बात ने बड़ा बदलाव ला दिया!",
    "जब उम्मीद ने हार नहीं मानी!",
    "यह अंत आपकी सोच बदल सकता है!",
    "कहानी का असली मतलब अंत में समझ आएगा!",
    "जो हुआ, उसकी किसी को उम्मीद नहीं थी!",
    "एक दिलचस्प कहानी जो आपको बांधे रखेगी!",
    "इस कहानी में हर पल नया मोड़ है!",
    "क्या अंत में सब ठीक हो पाएगा?",
    "एक ऐसा पल जिसने सब बदल दिया!",
    "कहानी का यह मोड़ याद रह जाएगा!",
    "आखिर किसकी बात सच निकली?",
    "एक मजेदार कहानी और शानदार ट्विस्ट! 😂",
    "आखिर तक देखिए, जवाब मिल जाएगा!",
    "इस कहानी को देखकर मुस्कुराना तय है!",
    "एक अनोखी सीख के साथ छोटी सी कहानी!",
    "जब एक राज ने पूरी कहानी बदल दी!",
    "इस कहानी में छुपा संदेश जरूर समझना!",
    "क्या आप इस कहानी का अंत समझ पाए?",
    "कभी-कभी सबसे बड़ा जवाब खामोशी होती है!",
    "यह कहानी आपको हैरान भी करेगी और हंसाएगी!",
    "एक अप्रत्याशित मोड़ जिसने सबको चौंका दिया!",
    "आखिर में मिला सबसे बड़ा सबक!",
    "इस कहानी को बीच में मत छोड़ना!",
    "एक छोटी कहानी, लेकिन बड़ी सीख!",
    "क्या सच में ऐसा हो सकता है?",
    "इस कहानी का ट्विस्ट लाजवाब है!",
    "जब सबने उम्मीद छोड़ दी, तभी चमत्कार हुआ!",
    "एक ऐसा फैसला जिसका असर सब पर पड़ा!",
    "कहानी का सबसे जरूरी हिस्सा अंत में है!",
    "आप होते तो क्या फैसला लेते?",
    "इस कहानी ने सबका नजरिया बदल दिया!",
    "अंत देखकर आप भी यही कहेंगे—वाह!",
    "किसी ने नहीं सोचा था कि ऐसा होगा!",
    "एक अनोखी घटना और उसका हैरान करने वाला अंत!",
    "यह कहानी आपको अंत तक रोके रखेगी!",
    "एक गलती और फिर शुरू हुई नई कहानी!",
    "सच्चाई सामने आते ही सब बदल गया!",
    "इस कहानी का जवाब आपको अंत में मिलेगा!",
    "एक दिलचस्प मोड़ जिसे मिस नहीं करना चाहिए!",
    "कहानी छोटी है, लेकिन बात बड़ी है!",
    "जब एक साधारण दिन बन गया यादगार!",
    "आखिर कौन सही था? कहानी देखिए!",
    "यह मोड़ देखकर आप चौंक जाएंगे!",
    "एक ऐसी सीख जो हर किसी को जाननी चाहिए!",
    "क्या आपने कहानी का छुपा हुआ संकेत देखा?",
    "आखिरकार इंतजार का फल मिल गया!",
    "इस कहानी में सबसे खास बात क्या थी?",
    "एक पल की समझदारी ने सब बदल दिया!",
    "यह कहानी आपको सोचने पर मजबूर करेगी!",
    "कहानी का अंत दिल जीत लेगा!",
    "ऐसा ट्विस्ट जिसकी उम्मीद नहीं थी!",
    "आखिर में खुला सबसे बड़ा रहस्य!",
    "एक नई कहानी, एक नया अनुभव!",
    "क्या आप अंत का अंदाजा लगा सकते हैं?",
    "इस कहानी में आगे बहुत कुछ होने वाला है!",
    "कभी हार मत मानना—यह कहानी यही सिखाती है!",
    "एक छोटा सा राज और बड़ा खुलासा!",
    "जो हुआ, उससे सब हैरान रह गए!",
    "यह कहानी आखिरी सेकंड तक देखना!",
    "एक मजेदार मोड़ जिसने माहौल बदल दिया!",
    "इस कहानी का असली हीरो कौन है?",
    "एक ऐसी बात जो देर से समझ आई!",
    "कहानी का अंत देखकर दिल खुश हो जाएगा!",
    "क्या आखिर में सच जीत पाएगा?",
    "एक अनोखी कहानी जिसे आप भूल नहीं पाएंगे!",
    "इस कहानी में छुपा है जिंदगी का सबक!",
    "आखिर ऐसा क्यों हुआ? जानिए पूरी कहानी!",
    "एक फैसला, और बदल गई पूरी दुनिया!",
    "किसी ने नहीं देखा था यह मोड़ आते हुए!",
    "यह छोटी सी कहानी बहुत कुछ कहती है!",
    "आखिरी पल में हुआ सबसे बड़ा खुलासा!",
    "कहानी का यह हिस्सा सबसे खास है!",
    "क्या आप इस रहस्य को सुलझा पाएंगे?",
    "एक ऐसी कहानी जिसका अंत याद रहेगा!",
    "जब सच्चाई ने सबको चुप करा दिया!",
    "इस कहानी में हंसी भी है और सीख भी!",
    "अंत तक देखिए—कहानी अभी बाकी है!",
    "एक अनोखा मोड़ और शानदार अंत!",
    "इस कहानी से मिलने वाली सीख अनमोल है!",
    "आखिर किस्मत ने क्या खेल खेला?",
    "एक पल ने सबकी जिंदगी बदल दी!",
    "इस कहानी का आखिरी सीन कमाल है!",
    "क्या आप भी यही सोच रहे थे?",
    "एक कहानी जो आपको अंत तक बांधे रखेगी!",
    "आखिरकार राज से पर्दा उठ ही गया!",
    "देखिए कैसे बदल गई पूरी कहानी!",
    "यह अंत बिल्कुल अप्रत्याशित था!",
    "कहानी का ट्विस्ट देखकर हो जाएंगे हैरान!",
    "एक छोटी सी कहानी, बड़ा सा संदेश!",
    "आखिर में जो सीख मिली, वह अनमोल है!",
]

DESCRIPTION_TEMPLATES = [
    (
        "देखिए JeetStoryAI की एक नई हिंदी कहानी! 🎬\n"
        "इस AI animated story में कहानी, मनोरंजन और एक दिलचस्प मोड़ आपका इंतजार कर रहा है। "
        "वीडियो को अंत तक देखें और बताएं कि आपको इसका कौन-सा हिस्सा सबसे अच्छा लगा।\n\n"
        "ऐसी ही Hindi stories, animated kahaniyan और entertaining Shorts के लिए "
        "JeetStoryAI को Subscribe करें। ❤️\n\n"
        "#Shorts #HindiStories #HindiKahani #AIAnimation #AnimatedStories "
        "#YouTubeShorts #ShortsFeed #ViralShorts"
    ),
    (
        "एक नई कहानी, एक नया अनुभव! 🍿\n"
        "JeetStoryAI पर देखिए Hindi storytelling और AI-generated animation का मजेदार संगम। "
        "अंत तक जरूर देखें—और अपनी राय Comment में बताएं!\n\n"
        "नई कहानियों के लिए Channel को Subscribe करें और वीडियो पसंद आए तो Like करें।\n\n"
        "#Shorts #HindiKahani #HindiStory #AIStory #3DAnimation "
        "#CartoonStories #ShortsFeed #ViralShorts"
    ),
    (
        "आपके लिए पेश है JeetStoryAI की एक और entertaining Hindi story! ✨\n"
        "यह animated short मनोरंजन के साथ एक दिलचस्प संदेश भी लेकर आया है। "
        "पूरा वीडियो देखें और बताएं: आपको इसका अंत कैसा लगा?\n\n"
        "ऐसी और Hindi animated stories के लिए JeetStoryAI से जुड़े रहें।\n\n"
        "#Shorts #HindiStories #AnimatedStory #AIAnimation #HindiCartoon "
        "#YTShorts #ShortsFeed #ViralShorts"
    ),
    (
        "कहानियों की दुनिया में आपका स्वागत है! 🎥\n"
        "JeetStoryAI पर मिलेंगी नई Hindi kahaniyan, AI animated stories और "
        "छोटे-छोटे मनोरंजक वीडियो। इस कहानी को अंत तक देखें!\n\n"
        "Like, Comment और Subscribe करना न भूलें। ❤️\n\n"
        "#Shorts #HindiKahaniyan #AIgenerated #AnimationVideo #StoryTime "
        "#YouTubeShorts #ShortsFeed #ViralShorts"
    ),
]

BASE_TAGS = [
    "JeetStoryAI",
    "hindi story",
    "hindi stories",
    "hindi kahani",
    "hindi kahaniya",
    "hindi kahaniyan",
    "animated stories",
    "hindi animated story",
    "ai story",
    "ai generated story",
    "ai animation",
    "3d animation",
    "hindi cartoon",
    "cartoon story",
    "moral stories",
    "short story",
    "storytelling",
    "hindi shorts",
    "youtube shorts",
    "shorts",
    "viral shorts",
    "shorts feed",
    "yt shorts",
    "entertainment",
    "story video",
    "animated video",
    "hindi animation",
    "new hindi story",
]


def generate_metadata(file_id, filename):
    """
    Generates broad Hindi storytelling metadata for JeetStoryAI.
    Titles are selected from a pool of 100+ general hooks, not from
    a particular topic or the original Drive filename.
    """

    seed = sum(ord(char) for char in file_id)
    rng = random.Random(seed)

    title = rng.choice(TITLE_POOL)
    description = rng.choice(DESCRIPTION_TEMPLATES)

    # Keep tags unique and within YouTube's practical tag-count limit.
    tags = list(dict.fromkeys(BASE_TAGS))[:30]

    return title[:100].strip(), description, tags


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
        prefix="jsai_",
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
    print("JEETSTORYAI - YOUTUBE AUTOMATION")
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
