# WhatHappensFactora YouTube Automation

This repository uploads **finished video files** from one Google Drive folder to the
WhatHappensFactora YouTube channel. It is intentionally separate from any other channel.

## Important: what this automation does

- Reads ready-to-upload videos from one Google Drive folder.
- Uploads at most one new video per workflow run.
- Uses the video filename (without extension) as the YouTube title.
- Applies the description, tags, and Education category from `config.json`.
- Tracks Google Drive file IDs in `upload_history.json` to avoid re-uploading the same file.
- Runs at 12:30 PM and 7:00 PM India time, plus manual runs.

**Claude is not called by this uploader.** Use Claude to research/prepare scripts and create
your finished videos separately, then put the final video files in the Drive folder. This
keeps upload automation separate from content generation and avoids silently publishing
unreviewed AI output.

## 1. Create a Google Drive folder

Create a folder such as `WhatHappensFactora/Ready Videos`. Upload finished MP4/MOV/WebM
video files there. Copy the folder ID from its URL:

`https://drive.google.com/drive/folders/FOLDER_ID`

Put that ID into `config.json` in place of `PASTE_GOOGLE_DRIVE_FOLDER_ID_HERE`.

## 2. Create Google OAuth credentials

1. Open https://console.cloud.google.com/ and create/select a Google Cloud project.
2. Enable **Google Drive API** and **YouTube Data API v3**.
3. Configure the OAuth consent screen. Add your Gmail as a test user if the app is in Testing.
4. Create an OAuth Client ID with application type **Desktop app**.
5. Download the JSON file and rename it `credentials.json`.
6. Put `credentials.json` in this project folder. Do not commit it.

## 3. Authorize the NEW channel account

Use a local computer with Python installed:

```bash
python -m pip install -r requirements.txt
python auth.py
```

On Windows, if `python` is unavailable, try:

```bash
py -m pip install -r requirements.txt
py auth.py
```

A browser window opens. Sign in specifically as `jeetsuthar148@gmail.com` and select the
WhatHappensFactora channel if YouTube asks which channel to authorize. Approve Drive read
and YouTube upload access. The script creates `token.json`.

If the account has multiple YouTube channels, verify the selected channel before continuing.
The token determines which channel receives uploads.

## 4. Add GitHub secrets and variables

Create a new **private** GitHub repository and upload the contents of this ZIP.

In the repository, open **Settings → Secrets and variables → Actions**.

Add this repository secret:

- `YOUTUBE_TOKEN_JSON` = open local `token.json` in Notepad, copy the entire JSON contents, paste as the secret value.

Add these repository variables:

- `DRIVE_FOLDER_ID` = the Google Drive folder ID.
- `YOUTUBE_PRIVACY_STATUS` = `private` for initial testing. Change to `public` only after verifying the workflow.

Do not add `credentials.json` or `token.json` to the repository.

## 5. Test safely

1. Keep `YOUTUBE_PRIVACY_STATUS` set to `private`.
2. Open **Actions → WhatHappensFactora YouTube Automation → Run workflow**.
3. Check the logs and confirm the video appears on the intended channel as Private.
4. Confirm the title, description, video, and channel are correct.
5. Only then change `YOUTUBE_PRIVACY_STATUS` to `public` if you want automatic public publishing.

## 6. What you may need to customize

- `config.json`: description, tags, category, folder ID, max uploads per run.
- GitHub Actions variables: Drive folder ID and privacy status.
- `.github/workflows/upload.yml`: upload times (currently 12:30 PM and 7:00 PM IST).

## Notes and limitations

- One upload per run by default. The two scheduled runs can upload up to two videos per day.
- Supported files are selected by Google Drive MIME type beginning with `video/`; common formats
  include MP4, MOV, and WebM. YouTube may reject unsupported codecs or malformed files.
- Titles are derived from filenames. Rename files clearly before placing them in the ready folder.
- This starter does not generate scripts, voiceovers, captions, thumbnails, or videos.
- OAuth access can expire or be revoked. If uploads start failing with authentication errors,
  regenerate `token.json` with `auth.py` and update the GitHub secret.
- YouTube API quota and channel/account eligibility limits still apply.
- Review facts, copyright, music rights, and AI-generated content before publishing.
