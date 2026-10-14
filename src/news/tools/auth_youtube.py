"""Interactive YouTube OAuth 2.0 Authorization & Diagnostics Utility.

Run this script to authenticate or refresh your YouTube credentials:
    uv run python -m news.tools.auth_youtube
"""

import sys
import logging
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import settings, ROOT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YouTubeAuth")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_PATH = ROOT_DIR / "data" / "client_secret.json"
TOKEN_PATH = ROOT_DIR / "data" / "token.json"


def test_existing_token() -> bool:
    """Test if the current token.json is valid or can be refreshed."""
    if not TOKEN_PATH.exists():
        logger.info(f"No token.json found at {TOKEN_PATH}")
        return False

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("Attempting to refresh existing credentials...")
                creds.refresh(Request())
                TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
                logger.info("Successfully refreshed and updated token.json!")

        # Verify API call
        youtube = build("youtube", "v3", credentials=creds)
        res = youtube.channels().list(part="snippet", mine=True).execute()
        channels = res.get("items", [])
        if channels:
            ch_title = channels[0]["snippet"]["title"]
            logger.info(f"SUCCESS: Authenticated with YouTube Channel: '{ch_title}'")
            return True
        else:
            logger.info("Token is valid, but no YouTube channel found for this Google account.")
            return True
    except Exception as e:
        logger.warning(f"Existing token is invalid or expired: {e}")
        return False


def run_oauth_flow():
    """Run interactive 1-time browser OAuth flow and save persistent token.json."""
    if not CLIENT_SECRET_PATH.exists():
        logger.error(f"client_secret.json not found at: {CLIENT_SECRET_PATH}")
        logger.error("Please download it from Google Cloud Console as described in YOUTUBE_API_SETUP_GUIDE.md")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" YouTube OAuth 2.0 Authorization Utility")
    print("=" * 70)
    print("Opening your default browser for 1-time Google sign-in...")
    print("1. Sign in with the Google Account that manages your YouTube channel.")
    print("2. If warned 'Google hasn't verified this app', click 'Advanced' -> 'Go to News Video Uploader (unsafe)'.")
    print("3. Check the permission box and click 'Continue'.")
    print("=" * 70 + "\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    logger.info(f"Saved fresh persistent credentials to: {TOKEN_PATH}")

    # Verify channel
    try:
        youtube = build("youtube", "v3", credentials=creds)
        res = youtube.channels().list(part="snippet", mine=True).execute()
        items = res.get("items", [])
        if items:
            title = items[0]["snippet"]["title"]
            print("\n" + "*" * 70)
            print(f" SUCCESS! Channel Linked: {title}")
            print("*" * 70)
        else:
            print("\n* Authentication complete! (No channel items returned)")
    except Exception as e:
        logger.warning(f"Note verifying channel: {e}")

    print("\n[CRITICAL NOTE FOR PERMANENT PRODUCTION TOKENS]:")
    print("To make this token permanent so Google never expires it:")
    print("1. Go to: https://console.cloud.google.com/apis/credentials/consent")
    print("2. Under 'Publishing status', click 'PUBLISH APP' and confirm.")
    print("This ensures your token never expires after 7 days!\n")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        run_oauth_flow()
        return

    logger.info("Testing existing YouTube token...")
    if test_existing_token():
        print("\nYour YouTube authentication is already healthy and active! No re-auth needed.")
        print("To force a re-login, run: uv run python -m news.tools.auth_youtube --force\n")
    else:
        logger.info("Proceeding with browser OAuth authorization...")
        run_oauth_flow()


if __name__ == "__main__":
    main()
