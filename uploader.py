
name: JeetStoryAI YouTube Automation

on:
  schedule:
    # 09:00, 12:00, 15:00, 18:00 and 21:00 IST
    # GitHub Actions cron uses UTC (IST is UTC+05:30).
    - cron: '30 3,6,9,12,15 * * *'

  workflow_dispatch:

permissions:
  contents: write

# Avoid two upload runs updating history simultaneously.
concurrency:
  group: jeetstoryai-youtube-upload-${{ github.ref }}
  cancel-in-progress: false

jobs:
  upload:
    runs-on: ubuntu-latest
    timeout-minutes: 90

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: ${{ github.ref_name }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install FFmpeg
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg
          ffmpeg -version
          ffprobe -version

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt

      - name: Create Google OAuth token file
        env:
          YOUTUBE_TOKEN_JSON: ${{ secrets.YOUTUBE_TOKEN_JSON }}
        run: |
          if [ -z "$YOUTUBE_TOKEN_JSON" ]; then
            echo "YOUTUBE_TOKEN_JSON secret is missing."
            exit 1
          fi

          printf '%s' "$YOUTUBE_TOKEN_JSON" > token.json

      - name: Upload one video
        env:
          DRIVE_FOLDER_ID: ${{ secrets.DRIVE_FOLDER_ID }}
          MAX_UPLOADS_PER_RUN: '1'
          DAILY_UPLOAD_LIMIT: '5'
        run: python -u uploader.py

      - name: Save upload history to repository
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

          if [ -f upload_history.json ]; then
            git add upload_history.json

            if ! git diff --cached --quiet; then
              git commit -m "Update JeetStoryAI upload history [skip ci]"
              git push
            else
              echo "Upload history has no changes."
            fi
          else
            echo "upload_history.json was not created."
          fi
