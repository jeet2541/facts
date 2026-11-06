from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Combined permissions: read videos from Drive and upload to YouTube.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]

ROOT = Path(__file__).resolve().parent
CLIENT_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token.json"

def main():
    if not CLIENT_FILE.exists():
        raise FileNotFoundError(
            "Download the OAuth Desktop app client JSON from Google Cloud and save it "
            "beside auth.py as credentials.json."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print("Authorization successful. token.json created.")
    print("Keep token.json private. Never upload it to GitHub.")

if __name__ == "__main__":
    main()
