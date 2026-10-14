"""YouTube Data API v3 Upload Engine.

Handles OAuth 2.0 authentication, token persistence, and resumable video uploads
with metadata (Title, Description, Tags, Category, Privacy, Kids setting).
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from ..config import settings, ROOT_DIR

logger = logging.getLogger(__name__)

# Scopes required to upload YouTube videos and manage playlists
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_PATH = ROOT_DIR / "data" / "client_secret.json"
TOKEN_PATH = ROOT_DIR / "data" / "token.json"

# YouTube Category ID 25 = News & Politics
CATEGORY_NEWS_AND_POLITICS = "25"


def calculate_youtube_publish_status(rank: int = 1) -> Dict[str, Any]:
    """Calculate YouTube publication schedule based on time-of-day policies.
    
    Publication Rules:
    - Default visibility: PUBLIC.
    - Clicked before 9:00 AM local time:
        - 1st video (rank 1): Scheduled to publish Public at 9:00 AM same day.
        - 2nd video (rank 2): Scheduled to publish Public at 9:15 AM same day.
    - Clicked 9:00 AM to 1:00 PM (13:00) local time:
        - Published immediately as Public at time of click.
    - Clicked 1:00 PM (13:00) to 6:00 PM (18:00) local time:
        - 1st video (rank 1): Scheduled to publish Public at 6:00 PM (18:00) same day.
        - 2nd video (rank 2): Scheduled to publish Public at 6:15 PM (18:15) same day.
    - Clicked after 6:00 PM (18:00) local time:
        - Published immediately as Public at time of click.
        
    Note: YouTube Data API requires privacyStatus='private' when publishAt is set.
    YouTube automatically transitions the video to 'public' when the scheduled timestamp arrives.
    """
    now_local = datetime.now().astimezone()
    hour = now_local.hour

    scheduled_dt = None
    schedule_desc = "Immediate Public release"

    if hour < 9:
        # Before 9 AM: Schedule 9:00 AM (Rank 1) or 9:15 AM (Rank 2)
        sched_min = 0 if rank <= 1 else 15
        target = now_local.replace(hour=9, minute=sched_min, second=0, microsecond=0)
        if target > now_local + timedelta(minutes=2):
            scheduled_dt = target
            t_str = "9:00 AM" if rank <= 1 else "9:15 AM"
            schedule_desc = f"Scheduled to publish Public at {t_str} today"
    elif 13 <= hour < 18:
        # 1 PM to 6 PM: Schedule 6:00 PM (Rank 1) or 6:15 PM (Rank 2)
        sched_min = 0 if rank <= 1 else 15
        target = now_local.replace(hour=18, minute=sched_min, second=0, microsecond=0)
        if target > now_local + timedelta(minutes=2):
            scheduled_dt = target
            t_str = "6:00 PM" if rank <= 1 else "6:15 PM"
            schedule_desc = f"Scheduled to publish Public at {t_str} today"

    if scheduled_dt:
        utc_dt = scheduled_dt.astimezone(timezone.utc)
        publish_at_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return {
            "privacyStatus": "private",  # Mandatory for YouTube API scheduled uploads
            "publishAt": publish_at_iso,
            "scheduled_local_str": scheduled_dt.strftime("%I:%M %p"),
            "schedule_description": schedule_desc,
            "is_scheduled": True,
            "target_visibility": "public",
        }
    else:
        return {
            "privacyStatus": "public",
            "publishAt": None,
            "scheduled_local_str": "Immediate",
            "schedule_description": "Published Public immediately",
            "is_scheduled": False,
            "target_visibility": "public",
        }

# In-memory progress tracking for real-time frontend feedback
# story_id -> { "status": "idle"|"authenticating"|"uploading"|"completed"|"failed", "progress": int, ... }
_upload_progress: Dict[str, Dict[str, Any]] = {}


def get_upload_progress(story_id: str) -> Dict[str, Any]:
    """Retrieve real-time upload progress for a story."""
    return _upload_progress.get(story_id, {
        "status": "idle",
        "progress": 0,
        "uploaded_bytes": 0,
        "total_bytes": 0,
        "message": "Ready to upload",
        "video_url": "",
        "video_id": "",
    })


def set_upload_progress(story_id: str, data: Dict[str, Any]):
    """Update progress tracking state for a story."""
    if story_id not in _upload_progress:
        _upload_progress[story_id] = {
            "status": "idle",
            "progress": 0,
            "uploaded_bytes": 0,
            "total_bytes": 0,
            "message": "",
            "video_url": "",
            "video_id": "",
            "error": "",
        }
    _upload_progress[story_id].update(data)


def get_youtube_credentials(
    client_secret_path: Optional[Path] = None,
    token_path: Optional[Path] = None,
    story_id: Optional[str] = None,
) -> Credentials:
    """Load existing token.json or prompt for 1-time local browser OAuth consent."""
    if client_secret_path is None:
        client_secret_path = CLIENT_SECRET_PATH
    if token_path is None:
        token_path = TOKEN_PATH

    creds = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if creds and not creds.has_scopes(SCOPES):
                logger.info("Existing token.json lacks updated scopes (e.g. playlist permissions). Re-authenticating...")
                creds = None
        except Exception as e:
            logger.warning(f"Existing token.json could not be loaded: {e}")
            creds = None

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired YouTube OAuth credentials...")
                creds.refresh(Request())
            except Exception as ref_err:
                logger.warning(f"Failed to refresh credentials: {ref_err}")
                creds = None

        if not creds:
            if not client_secret_path.exists():
                raise FileNotFoundError(
                    f"client_secret.json not found at '{client_secret_path}'. "
                    f"Please follow YOUTUBE_API_SETUP_GUIDE.md to place it in data/."
                )

            if story_id:
                set_upload_progress(story_id, {
                    "status": "authenticating",
                    "progress": 0,
                    "message": "Awaiting 1-time Google sign-in in browser...",
                })

            logger.info("Initiating 1-time local browser OAuth flow for YouTube...")
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

        # Save credentials for future silent runs
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info(f"Saved persistent YouTube credentials to: {token_path}")

    return creds


def get_youtube_client(
    client_secret_path: Optional[Path] = None,
    token_path: Optional[Path] = None,
    story_id: Optional[str] = None,
):
    """Build and return an authorized YouTube Data API v3 service resource."""
    creds = get_youtube_credentials(client_secret_path, token_path, story_id=story_id)
    return build("youtube", "v3", credentials=creds)


def parse_metadata_file(metadata_path: Path) -> Dict[str, Any]:
    """Parse key-value metadata from standard metadata.txt format."""
    text = metadata_path.read_text(encoding="utf-8")

    title_match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Broadcast News Update"

    # Extract description block (from Description: up to [PLAYLISTS])
    desc_match = re.search(r"^Description:\s*(.*?)(?=\n\[PLAYLISTS\]|\n\[AUDIENCE|\Z)", text, re.DOTALL | re.MULTILINE)
    description = desc_match.group(1).strip() if desc_match else ""

    # Tags
    tags_match = re.search(r"^Tags:\s*(.+)$", text, re.MULTILINE)
    tags = [t.strip() for t in tags_match.group(1).split(",") if t.strip()] if tags_match else ["news", "latest news"]

    # Audience / Kids
    kids_match = re.search(r"^IsMadeForKids:\s*(true|false)", text, re.IGNORECASE | re.MULTILINE)
    made_for_kids = kids_match.group(1).lower() == "true" if kids_match else False

    # Visibility / Privacy
    priv_match = re.search(r"^PrivacyStatus:\s*(private|unlisted|public)", text, re.IGNORECASE | re.MULTILINE)
    privacy_status = priv_match.group(1).lower() if priv_match else "public"

    # Playlist
    pl_match = re.search(r"^Playlists?:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    playlist = pl_match.group(1).strip() if pl_match else None
    if playlist:
        if "," in playlist:
            playlist = playlist.split(",")[0].strip()
        if "(" in playlist:
            playlist = playlist.split("(")[0].strip()

    # Video Language
    lang_match = re.search(r"^VideoLanguage:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    video_language = lang_match.group(1).strip() if lang_match else "en-IN"

    # Paid Promotion
    promo_match = re.search(r"^PaidPromotion:\s*(true|false)", text, re.IGNORECASE | re.MULTILINE)
    has_paid_promotion = promo_match.group(1).lower() == "true" if promo_match else False

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "made_for_kids": made_for_kids,
        "privacy_status": privacy_status,
        "playlist": playlist,
        "playlists": playlist,
        "video_language": video_language,
        "has_paid_promotion": has_paid_promotion,
    }


def upload_video_to_youtube(
    video_path: Path,
    metadata_path: Optional[Path] = None,
    client_secret_path: Optional[Path] = None,
    token_path: Optional[Path] = None,
    story_id: Optional[str] = None,
    rank: int = 1,
) -> Dict[str, Any]:
    """Upload an MP4 video file directly to YouTube with automated publication scheduling.

    Rules:
    - Default visibility: PUBLIC.
    - Clicked before 9:00 AM:
        - Rank 1: Scheduled to publish Public at 9:00 AM today.
        - Rank 2: Scheduled to publish Public at 9:15 AM today.
    - Clicked 9:00 AM to 1:00 PM:
        - Published immediately as Public at time of click.
    - Clicked 1:00 PM to 6:00 PM:
        - Rank 1: Scheduled to publish Public at 6:00 PM today.
        - Rank 2: Scheduled to publish Public at 6:15 PM today.
    - Clicked after 6:00 PM:
        - Published immediately as Public at time of click.

    Returns:
        dict: {"status": "success", "video_id": "...", "video_url": "https://youtu.be/...", "schedule_description": "...", ...}
    """
    if not video_path.exists():
        if story_id:
            set_upload_progress(story_id, {"status": "failed", "progress": 0, "message": "Video file not found"})
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    # Parse metadata if available, otherwise fallback
    if metadata_path and metadata_path.exists():
        meta = parse_metadata_file(metadata_path)
    else:
        # Check if metadata.txt exists alongside video
        candidate_meta = video_path.parent / "metadata.txt"
        if candidate_meta.exists():
            meta = parse_metadata_file(candidate_meta)
        else:
            meta = {
                "title": video_path.stem.replace("_", " "),
                "description": "Daily verified news intelligence broadcast.",
                "tags": ["GlobalBharatNews", "WorldNews", "IndiaNews", "NewsUpdate"],
                "made_for_kids": False,
                "privacy_status": "public",
            }

    file_size = video_path.stat().st_size
    publish_info = calculate_youtube_publish_status(rank=rank)

    if story_id:
        set_upload_progress(story_id, {
            "status": "uploading",
            "progress": 0,
            "uploaded_bytes": 0,
            "total_bytes": file_size,
            "schedule_info": publish_info,
            "message": f"Connecting to YouTube API ({publish_info['schedule_description']})...",
        })

    try:
        youtube = get_youtube_client(client_secret_path, token_path, story_id=story_id)

        # Build status block with publishAt if scheduled
        status_block = {
            "privacyStatus": publish_info["privacyStatus"],
            "selfDeclaredMadeForKids": meta.get("made_for_kids", False),
            "embeddable": True,
            "license": "youtube",
        }
        if publish_info.get("publishAt"):
            status_block["publishAt"] = publish_info["publishAt"]

        lang = meta.get("video_language") or "en-IN"
        body = {
            "snippet": {
                "title": meta["title"][:100],
                "description": meta["description"][:5000],
                "tags": meta["tags"][:40],
                "categoryId": CATEGORY_NEWS_AND_POLITICS,
                "defaultLanguage": lang,
                "defaultAudioLanguage": lang,
            },
            "status": status_block,
            "paidProductPlacementDetails": {
                "hasPaidProductPlacement": meta.get("has_paid_promotion", False),
            },
        }

        logger.info(
            f"Initiating YouTube upload for '{video_path.name}' "
            f"(Rank: {rank}, Policy: {publish_info['schedule_description']})..."
        )
        media = MediaFileUpload(
            str(video_path.resolve()),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 2,  # 2 MB chunks for granular percentage updates
        )

        request = youtube.videos().insert(
            part="snippet,status,paidProductPlacementDetails",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
            except Exception as chunk_err:
                err_str = str(chunk_err)
                # If YouTube rejects paidProductPlacementDetails in insert part, fallback safely to snippet,status
                if "paidProductPlacementDetails" in err_str:
                    logger.warning(f"YouTube rejected paidProductPlacementDetails on insert ({err_str}). Retrying with part='snippet,status'...")
                    media = MediaFileUpload(str(video_path.resolve()), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 2)
                    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
                    status, response = request.next_chunk()
                # If YouTube rejects scheduling for channel (e.g. phone verification required), fallback to immediate Public
                elif publish_info.get("publishAt") and ("publishAt" in err_str or "scheduled" in err_str.lower()):
                    logger.warning(f"YouTube rejected publishAt ({chunk_err}). Retrying upload as immediate Public...")
                    publish_info = {
                        "privacyStatus": "public",
                        "publishAt": None,
                        "scheduled_local_str": "Immediate",
                        "schedule_description": "Published Public immediately (Schedule fallback)",
                        "is_scheduled": False,
                        "target_visibility": "public",
                    }
                    body["status"] = {
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": meta.get("made_for_kids", False),
                        "embeddable": True,
                        "license": "youtube",
                    }
                    media = MediaFileUpload(str(video_path.resolve()), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 2)
                    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
                    status, response = request.next_chunk()
                else:
                    raise

            if status:
                progress_pct = min(99, max(1, int(status.progress() * 100)))
                uploaded_mb = round(status.resumable_progress / (1024 * 1024), 1)
                total_mb = round(status.total_size / (1024 * 1024), 1)
                msg = f"Uploading to YouTube: {progress_pct}% ({uploaded_mb} MB / {total_mb} MB) - {publish_info['schedule_description']}"
                logger.info(f"YouTube upload progress for '{video_path.name}': {progress_pct}% ({uploaded_mb}/{total_mb} MB)")
                if story_id:
                    set_upload_progress(story_id, {
                        "status": "uploading",
                        "progress": progress_pct,
                        "uploaded_bytes": status.resumable_progress,
                        "total_bytes": status.total_size,
                        "schedule_info": publish_info,
                        "message": msg,
                    })

        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        logger.info(f"Successfully uploaded video to YouTube! ID: {video_id} -> {video_url} ({publish_info['schedule_description']})")

        # 1. Automatically set high-CTR custom thumbnail if available
        thumbnail_path = video_path.parent / "thumbnail.jpg"
        if thumbnail_path.exists():
            try:
                logger.info(f"Setting custom high-CTR thumbnail for video {video_id}...")
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path.resolve()), mimetype="image/jpeg"),
                ).execute()
                logger.info("Custom thumbnail uploaded successfully!")
            except Exception as thumb_err:
                logger.warning(f"Could not set custom thumbnail (channel may need phone verification): {thumb_err}")

        # 2. Automatically post interactive discussion comment
        try:
            comment_text = (
                f"📢 DISCUSS: What is your perspective on this development?\n"
                f"Share your insights or questions in the comments below!\n\n"
                f"✅ Verified independent journalism dispatches. Full sources cited in description."
            )
            youtube.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": comment_text
                            }
                        }
                    }
                }
            ).execute()
            logger.info(f"Automated engagement comment posted for video {video_id}")
        except Exception as c_err:
            logger.debug(f"Automated comment note: {c_err}")

        # 3. Explicitly verify Paid Promotion setting ("No, my video doesn't include paid promotion")
        try:
            youtube.videos().update(
                part="paidProductPlacementDetails",
                body={
                    "id": video_id,
                    "paidProductPlacementDetails": {
                        "hasPaidProductPlacement": meta.get("has_paid_promotion", False),
                    }
                }
            ).execute()
            logger.info(f"Paid promotion setting confirmed ('No, my video doesn't include paid promotion') for video {video_id}")
        except Exception as promo_err:
            logger.debug(f"Paid promotion update note: {promo_err}")

        # 4. Automatically add to playlist
        playlist_name = meta.get("playlist") or meta.get("playlists")
        if not playlist_name or str(playlist_name).strip().lower() in ["none", ""]:
            title_text = f"{meta.get('title', '')} {meta.get('description', '')}".lower()
            if "india" in title_text or "bharat" in title_text or "delhi" in title_text:
                playlist_name = "Top 9AM news from INDIA"
            else:
                playlist_name = "World wide top 5 news for today"

        playlist_name = str(playlist_name).strip()
        logger.info(f"Target playlist for video {video_id}: '{playlist_name}'")

        try:
            pl_request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
            pl_response = pl_request.execute()
            target_pl_id = None
            norm_target = playlist_name.lower().strip()

            for item in pl_response.get("items", []):
                item_title = item.get("snippet", {}).get("title", "").strip().lower()
                if item_title == norm_target or norm_target in item_title or item_title in norm_target:
                    target_pl_id = item["id"]
                    logger.info(f"Matched existing playlist '{item.get('snippet', {}).get('title')}' (ID: {target_pl_id})")
                    break

            if not target_pl_id:
                logger.info(f"Playlist '{playlist_name}' not found on channel. Creating new playlist...")
                new_pl = youtube.playlists().insert(
                    part="snippet,status",
                    body={
                        "snippet": {
                            "title": playlist_name,
                            "description": f"Verified daily broadcasts for {playlist_name}.",
                        },
                        "status": {"privacyStatus": "public"},
                    }
                ).execute()
                target_pl_id = new_pl.get("id")
                logger.info(f"Created new playlist '{playlist_name}' with ID: {target_pl_id}")

            if target_pl_id:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": target_pl_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            }
                        }
                    }
                ).execute()
                logger.info(f"Video {video_id} successfully added to playlist '{playlist_name}' (ID: {target_pl_id})")
        except Exception as pl_err:
            logger.warning(f"Playlist assignment note for '{playlist_name}': {pl_err}")

        if story_id:
            set_upload_progress(story_id, {
                "status": "completed",
                "progress": 100,
                "uploaded_bytes": file_size,
                "total_bytes": file_size,
                "video_id": video_id,
                "video_url": video_url,
                "schedule_info": publish_info,
                "message": f"Upload complete! {publish_info['schedule_description']} (Video ID: {video_id})",
            })

        return {
            "status": "success",
            "video_id": video_id,
            "video_url": video_url,
            "title": meta["title"],
            "privacy_status": publish_info["privacyStatus"],
            "is_scheduled": publish_info["is_scheduled"],
            "schedule_description": publish_info["schedule_description"],
            "schedule_time": publish_info["scheduled_local_str"],
        }
    except Exception as e:
        if story_id:
            set_upload_progress(story_id, {
                "status": "failed",
                "progress": 0,
                "error": str(e),
                "message": f"Upload failed: {str(e)}",
            })
        raise


def check_youtube_auth_status() -> Dict[str, Any]:
    """Check configuration and authentication readiness for YouTube uploading."""
    has_client_secret = CLIENT_SECRET_PATH.exists()
    has_token = TOKEN_PATH.exists()

    is_authenticated = False
    if has_token:
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            is_authenticated = bool(creds and (creds.valid or creds.refresh_token))
        except Exception:
            is_authenticated = False

    return {
        "client_secret_configured": has_client_secret,
        "authenticated": is_authenticated,
        "client_secret_path": str(CLIENT_SECRET_PATH),
        "token_path": str(TOKEN_PATH),
    }
