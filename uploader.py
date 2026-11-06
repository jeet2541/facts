
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

    # Important: Do not let httplib2 treat YouTube's
    # resumable-upload HTTP 308 response as a redirect.
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
