
import os
import re
import json
import time
import random
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

# Maximum uploads allowed in one execution
MAX_UPLOADS_PER_RUN = int(os.getenv("MAX_UPLOADS_PER_RUN", "5"))

# Maximum total uploads allowed per Indian calendar day
DAILY_UPLOAD_LIMIT = int(os.getenv("DAILY_UPLOAD_LIMIT", "5"))

TIMEZONE = ZoneInfo("Asia/Kolkata")

MAX_SHORT_DURATION = 180
CHUNK_SIZE = 8 * 1024 * 1024

CHANNEL_NAME = "JeetStoryAI"

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm",
    ".wmv", ".flv", ".3gp", ".3g2", ".mpeg", ".mpg",
    ".mpe", ".mpv", ".m2v", ".mts", ".m2ts", ".ts",
    ".vob", ".ogv", ".divx", ".f4v", ".asf", ".mxf",
}


# ============================================================
# HINGLISH TITLE GENERATOR
# ============================================================

TITLE_POOL = [
    "Aakhir Mein Jo Hua, Kisi Ne Socha Bhi Nahi Tha! 😱",
    "Is Kahani Ka End Aapko Hairan Kar Dega! 🤯",
    "Ek Aisi Kahani Jo Dil Chhoo Jayegi ❤️",
    "Aakhir Sach Kya Tha? Puri Story Dekho!",
    "Jab Kismat Ne Achanak Palti Maari! 😲",
    "Is Kahani Mein Chhupa Hai Ek Bada Twist!",
    "Last Tak Dekhna, Asli Twist Abhi Baaki Hai! 😳",
    "Kabhi Kabhi Sach Imagination Se Bhi Ajeeb Hota Hai!",
    "Ek Chhota Sa Decision Aur Sab Kuch Badal Gaya!",
    "Jo Dikhta Hai, Hamesha Wahi Sach Nahi Hota!",
    "Iska Ending Bilkul Unexpected Hai! 😮",
    "Ek Unique Story Aur Ek Shocking Twist!",
    "Aage Jo Hua, Dekhkar Yakeen Nahi Hoga!",
    "Is Kahani Ne Sabko Sochne Par Majboor Kar Diya!",
    "Ek Pal Mein Badal Gayi Puri Kahani!",
    "End Tak Wait Karna, Twist Zabardast Hai!",
    "Aakhir Khul Hi Gaya Sabse Bada Raaz!",
    "Aisa Twist Aapne Pehle Kabhi Nahi Dekha Hoga!",
    "Kabhi Kisi Ko Kam Mat Samajhna!",
    "Ek Seekh Jo Zindagi Bhar Yaad Rahegi!",
    "Is Story Se Aapko Bhi Kuch Seekhne Milega!",
    "Ending Dekhkar Aapka Dil Khush Ho Jayega! 😊",
    "Ek Aisa Secret Jisne Sabko Hila Diya!",
    "Jab Sabke Saamne Aaya Asli Sach!",
    "Aage Jo Hua Woh Sach Mein Kamaal Tha!",
    "Ek Anokha Safar Aur Ek Yaadgaar Seekh!",
    "Kya Aapne Kabhi Aisa Socha Tha?",
    "Is Kahani Ko End Tak Zaroor Dekhna!",
    "Aakhir Use Apni Galti Samajh Aa Hi Gayi!",
    "Ek Story, Kai Emotions Aur Ek Bada Twist!",
    "Sab Normal Tha... Phir Achanak Ye Hua!",
    "Last 5 Seconds Miss Mat Karna! 😱",
    "Is Kahani Ka Message Bahut Special Hai!",
    "Ek Chhoti Si Baat Ne Sab Badal Diya!",
    "Jab Umeed Ne Haar Nahi Maani!",
    "Ye Ending Aapki Soch Badal Sakti Hai!",
    "Story Ka Asli Meaning End Mein Samajh Aayega!",
    "Jo Hua Uski Kisi Ko Umeed Nahi Thi!",
    "Ek Interesting Story Jo Aapko Baandh Kar Rakhegi!",
    "Is Kahani Mein Har Pal Naya Twist Hai!",
    "Kya End Mein Sab Theek Ho Payega?",
    "Ek Aisa Moment Jisne Sab Kuch Badal Diya!",
    "Kahani Ka Ye Twist Yaad Reh Jayega!",
    "Aakhir Kiski Baat Sach Nikli?",
    "Ek Funny Story Aur Zabardast Twist! 😂",
    "End Tak Dekho, Jawab Mil Jayega!",
    "Is Story Ko Dekhkar Smile Aa Jayegi!",
    "Ek Chhoti Kahani Aur Ek Badi Seekh!",
    "Jab Ek Raaz Ne Puri Kahani Badal Di!",
    "Is Kahani Mein Chhupa Message Samajhna!",
    "Kya Aap Story Ka Ending Guess Kar Sakte Ho?",
    "Kabhi Kabhi Sabse Bada Jawab Khamoshi Hoti Hai!",
    "Ye Story Aapko Hairan Bhi Karegi Aur Hasayegi!",
    "Ek Unexpected Twist Jisne Sabko Chonka Diya!",
    "Aakhir Mein Mili Sabse Badi Seekh!",
    "Is Kahani Ko Beech Mein Mat Chhodna!",
    "Ek Chhoti Story, Lekin Baat Bahut Badi!",
    "Kya Sach Mein Aisa Ho Sakta Hai?",
    "Is Kahani Ka Twist Lajawaab Hai!",
    "Jab Sabne Umeed Chhod Di, Tab Chamatkar Hua!",
    "Ek Decision Jiska Asar Sab Par Pada!",
    "Story Ka Sabse Important Part End Mein Hai!",
    "Aap Hote Toh Kya Decision Lete?",
    "Is Kahani Ne Sabka Nazariya Badal Diya!",
    "Ending Dekhkar Aap Bhi Kahoge WOW!",
    "Kisi Ne Nahi Socha Tha Aisa Hoga!",
    "Ek Anokhi Ghatna Aur Hairan Karne Wala End!",
    "Ye Story Aapko Last Tak Rok Kar Rakhegi!",
    "Ek Galti Aur Shuru Hui Nayi Kahani!",
    "Sach Saamne Aate Hi Sab Badal Gaya!",
    "Is Kahani Ka Jawab End Mein Milega!",
    "Ek Interesting Twist Jo Miss Nahi Karna!",
    "Story Chhoti Hai, Lekin Baat Badi Hai!",
    "Jab Ek Normal Din Ban Gaya Yaadgaar!",
    "Aakhir Kaun Sahi Tha? Story Dekho!",
    "Ye Twist Dekhkar Aap Bhi Chonk Jaoge!",
    "Ek Aisi Seekh Jo Har Kisi Ko Janni Chahiye!",
    "Kya Aapne Story Ka Hidden Clue Dekha?",
    "Aakhirkar Intezaar Ka Result Mil Gaya!",
    "Is Kahani Ki Sabse Special Baat Kya Thi?",
    "Ek Pal Ki Samajhdari Ne Sab Badal Diya!",
    "Ye Story Aapko Sochne Par Majboor Karegi!",
    "Is Kahani Ka Ending Dil Jeet Lega!",
    "Aisa Twist Jiski Kisi Ko Umeed Nahi Thi!",
    "Aakhir Khul Gaya Sabse Bada Secret!",
    "Ek Nayi Story, Ek Naya Experience!",
    "Kya Aap Ending Ka Andaza Laga Sakte Ho?",
    "Is Kahani Mein Aage Bahut Kuch Hone Wala Hai!",
    "Kabhi Haar Mat Maanna! ❤️",
    "Ek Chhota Sa Secret Aur Bada Khulasa!",
    "Jo Hua, Usse Sab Hairan Reh Gaye!",
    "Ye Kahani Last Second Tak Dekhna!",
    "Ek Funny Twist Ne Sabka Mood Badal Diya!",
    "Is Story Ka Asli Hero Kaun Hai?",
    "Ek Aisi Baat Jo Der Se Samajh Aayi!",
    "Ending Dekhkar Dil Khush Ho Jayega!",
    "Kya Aakhir Mein Sach Jeet Payega?",
    "Ek Unique Story Jo Aap Bhool Nahi Paoge!",
    "Is Kahani Mein Chhupi Hai Life Ki Seekh!",
    "Aakhir Aisa Kyun Hua? Puri Story Dekho!",
    "Ek Decision Aur Badal Gayi Puri Duniya!",
    "Kisi Ne Ye Twist Aate Hue Nahi Dekha!",
    "Ye Chhoti Si Story Bahut Kuch Kehti Hai!",
    "Last Moment Par Hua Sabse Bada Khulasa!",
    "Kahani Ka Ye Hissa Sabse Special Hai!",
    "Kya Aap Is Mystery Ko Solve Kar Paoge?",
    "Ek Aisi Kahani Jiska End Yaad Rahega!",
    "Jab Sach Ne Sabko Khamosh Kar Diya!",
    "Is Story Mein Comedy Bhi Hai Aur Seekh Bhi!",
    "End Tak Dekho, Kahani Abhi Baaki Hai!",
    "Ek Zabardast Twist Aur Amazing Ending!",
    "Is Kahani Ki Seekh Bahut Anmol Hai!",
    "Aakhir Kismat Ne Kya Game Khela?",
    "Ek Moment Ne Sabki Life Badal Di!",
    "Is Story Ka Last Scene Kamaal Hai!",
    "Kya Aap Bhi Yahi Soch Rahe The?",
    "Ek Kahani Jo Aapko End Tak Baandhe Rakhegi!",
    "Aakhir Raaz Se Parda Uth Hi Gaya!",
    "Dekho Kaise Badal Gayi Puri Kahani!",
    "Ye Ending Bilkul Unexpected Thi!",
    "Story Ka Twist Dekhkar Hairan Ho Jaoge!",
    "Ek Chhoti Kahani, Ek Bada Message!",
    "Aakhir Mein Jo Seekh Mili, Woh Anmol Hai!",
]


# ============================================================
# HINGLISH DESCRIPTION GENERATOR
# ============================================================

DESCRIPTION_TEMPLATES = [
    (
        "Ek nayi kahani, ek naya experience! 🎬\n\n"
        "JeetStoryAI par dekho AI animated Hindi stories, interesting "
        "kahaniyan aur zabardast twists.\n\n"
        "Video ko end tak dekho aur comment mein batao ki tumhe story kaisi lagi!\n\n"
        "Aisi hi entertaining stories ke liye JeetStoryAI ko Subscribe karo! ❤️\n\n"
        "#Shorts #HindiStories #HindiKahani #AIAnimation "
        "#AnimatedStories #YouTubeShorts"
    ),
    (
        "Kahaniyon ki duniya mein aapka welcome hai! 🍿\n\n"
        "Yahan milegi AI animation ke saath entertaining Hindi storytelling. "
        "Har story mein kuch naya dekhne ko milega.\n\n"
        "Puri video dekho aur apni opinion comment karo!\n\n"
        "JeetStoryAI ko Subscribe karna mat bhoolna.\n\n"
        "#Shorts #HindiKahani #AIStory #HindiAnimation "
        "#CartoonStories #ShortsFeed"
    ),
    (
        "Aapke liye JeetStoryAI ki ek aur interesting story! ✨\n\n"
        "AI generated animation aur Hindi storytelling ka ek naya experience. "
        "Story ko last tak zaroor dekhna.\n\n"
        "Aapko ending kaisi lagi? Comment mein batao!\n\n"
        "Like aur Subscribe zaroor karna. ❤️\n\n"
        "#Shorts #HindiStories #AnimatedStory #AIAnimation "
        "#HindiCartoon #YouTubeShorts"
    ),
    (
        "Ready ho ek aur interesting kahani ke liye? 🎥\n\n"
        "JeetStoryAI par dekho entertaining animated stories, unexpected "
        "twists aur interesting storytelling.\n\n"
        "Video ko end tak dekho aur apne friends ke saath share karo!\n\n"
        "More stories ke liye Subscribe karo.\n\n"
        "#Shorts #HindiKahaniyan #AIgenerated #AnimationVideo "
        "#StoryTime #ShortsFeed"
    ),
    (
        "Har kahani ke peeche hoti hai ek nayi baat! ❤️\n\n"
        "JeetStoryAI lekar aata hai AI animated Hindi stories aur "
        "entertaining short videos.\n\n"
        "Aapko story ka sabse best part kaunsa laga? Comment karo!\n\n"
        "Channel ko Subscribe karke hamare saath jude raho.\n\n"
        "#Shorts #HindiStory #HindiKahani #AIAnimation "
        "#AnimatedStories #YTShorts"
    ),
    (
        "Aaj ki story dekhne ke liye ready ho? 😍\n\n"
        "JeetStoryAI par enjoy karo Hindi animated kahaniyan aur "
        "AI storytelling ka unique experience.\n\n"
        "Last tak dekhna, kyunki kahani ka ending interesting ho sakta hai!\n\n"
        "Like, Share aur Subscribe karo!\n\n"
        "#Shorts #HindiStories #HindiAnimation #AIStory "
        "#CartoonAnimation #YouTubeShorts"
    ),
]


# ============================================================
# SEO TAGS
# ============================================================

BASE_TAGS = [
    "JeetStoryAI",
    "hindi story",
    "hindi stories",
    "hindi kahani",
    "hindi kahaniya",
    "hindi kahaniyan",
    "hinglish stories",
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
    Creates generic Hinglish titles and descriptions.
    Selection is deterministic for each Drive file ID.
    """

    seed = sum(ord(char) for char in file_id)
    rng = random.Random(seed)

    title = rng.choice(TITLE_POOL)
    description = rng.choice(DESCRIPTION_TEMPLATES)

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
        return {
            "uploaded_file_ids": [],
            "uploaded_files": [],
        }

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as history_file:
            data = json.load(history_file)

    except (json.JSONDecodeError, OSError):
        raise RuntimeError(
            "Upload history could not be read. "
            "Stopping to prevent duplicate uploads."
        )

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
        raise RuntimeError("Invalid upload history format.")

    ids = data.get("uploaded_file_ids", [])

    if not isinstance(ids, list):
        ids = []

    old_items = data.get("uploaded_files", [])

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

        json.dump(
            history,
            history_file,
            indent=2,
            ensure_ascii=False,
        )

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
# DAILY UPLOAD COUNTER
# ============================================================

def count_uploads_today(history):

    today = datetime.now(TIMEZONE).date()

    count = 0

    for record in history.get("uploaded_files", []):

        if not isinstance(record, dict):
            continue

        uploaded_at = record.get("uploaded_at")

        if not uploaded_at:
            continue

        try:

            uploaded_time = datetime.fromisoformat(
                uploaded_at.replace("Z", "+00:00")
            )

            if uploaded_time.tzinfo is None:
                uploaded_time = uploaded_time.replace(
                    tzinfo=timezone.utc
                )

            local_date = uploaded_time.astimezone(TIMEZONE).date()

            if local_date == today:
                count += 1

        except (ValueError, TypeError):
            print(
                "WARNING: Invalid upload date in history:",
                uploaded_at,
            )

    return count


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

    request = drive_service.files().get_media(
        fileId=file_id
    )

    with open(filepath, "wb") as output_file:

        downloader = MediaIoBaseDownload(
            output_file,
            request,
            chunksize=CHUNK_SIZE,
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

        duration = float(
            info.get("format", {}).get("duration", 0)
        )

        streams = info.get("streams", [])

        if not streams:
            return False, "No video stream found"

        stream = streams[0]

        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))

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

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):

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

def upload_to_youtube(
    youtube_service,
    filepath,
    title,
    description,
    tags,
):

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

    print(
        f"Video URL: https://www.youtube.com/watch?v={video_id}"
    )

    return video_id


# ============================================================
# MAIN AUTOMATION
# ============================================================

def main():

    if not DRIVE_FOLDER_ID:
        raise RuntimeError(
            "DRIVE_FOLDER_ID environment variable is missing."
        )

    if MAX_UPLOADS_PER_RUN < 1:
        raise ValueError(
            "MAX_UPLOADS_PER_RUN must be at least 1."
        )

    if DAILY_UPLOAD_LIMIT < 1:
        raise ValueError(
            "DAILY_UPLOAD_LIMIT must be at least 1."
        )

    print("=" * 55)
    print("JEETSTORYAI - YOUTUBE AUTOMATION")
    print("=" * 55)

    print("Daily upload limit:", DAILY_UPLOAD_LIMIT)
    print("Maximum uploads per run:", MAX_UPLOADS_PER_RUN)

    credentials = get_credentials()

    drive_service = create_drive_service(credentials)

    youtube_service = create_youtube_service(credentials)

    history = load_history()

    uploaded_ids = set(history["uploaded_file_ids"])

    # Count uploads already completed today.
    uploaded_today = count_uploads_today(history)

    remaining_today = max(
        0,
        DAILY_UPLOAD_LIMIT - uploaded_today,
    )

    print("\nToday's upload status:")
    print("Already uploaded today:", uploaded_today)
    print("Remaining daily uploads:", remaining_today)

    if remaining_today <= 0:

        print("\nDaily upload limit reached.")
        print("No more uploads will be done today.")

        return

    # Limit this run AND the entire day.
    allowed_this_run = min(
        MAX_UPLOADS_PER_RUN,
        remaining_today,
    )

    print("Allowed uploads in this run:", allowed_this_run)

    videos = list_drive_videos(drive_service)

    pending_videos = [
        video for video in videos
        if video["id"] not in uploaded_ids
    ]

    print("\nAlready uploaded (all time):", len(uploaded_ids))
    print("Pending videos:", len(pending_videos))

    if not pending_videos:

        print("No pending videos found.")

        return

    successful_uploads = 0

    for video in pending_videos:

        if successful_uploads >= allowed_this_run:
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

            # Save successful upload immediately.
            mark_as_uploaded(
                history,
                file_id,
                filename,
                video_id,
            )

            successful_uploads += 1

            uploaded_today += 1

            print(
                f"Today's completed uploads: "
                f"{uploaded_today}/{DAILY_UPLOAD_LIMIT}"
            )

        except Exception as error:

            print(
                f"ERROR processing {filename}: {error}"
            )

            raise

        finally:

            if filepath and os.path.exists(filepath):

                try:
                    os.remove(filepath)

                except OSError:
                    pass

    print("\n" + "=" * 55)
    print("JEETSTORYAI RUN COMPLETED")
    print("=" * 55)

    print("Successful uploads this run:", successful_uploads)
    print("Total uploads today:", uploaded_today)
    print("Daily limit:", DAILY_UPLOAD_LIMIT)

    print("=" * 55)


if __name__ == "__main__":
    main()
