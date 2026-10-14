"""Automated Facebook & Instagram Video Uploader for AI News Platform.

Features:
- Facebook Pages: Resumable chunked video upload directly to Facebook Page via Meta Graph API v21.0.
  Custom thumbnail attachment, title, description, and hashtags.
- Instagram Professional/Creator: Resumable container video upload via Instagram Graph API.
  Automatic status polling, caption formatting with hashtags, and final publishing.
- Safe isolation: Standalone module; zero dependency or interference with YouTube uploader.
- Flexible configuration: Loads credentials from data/meta_credentials.json or environment variables.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")
    load_dotenv(Path(".env"))
except ImportError:
    pass

logger = logging.getLogger("news.meta_uploader")
logger.setLevel(logging.INFO)

GRAPH_API_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
GRAPH_VIDEO_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"

DEFAULT_CREDENTIALS_PATH = Path("data/meta_credentials.json")

# In-memory progress tracking for asynchronous uploads
_fb_upload_progress: Dict[str, Dict[str, Any]] = {}
_ig_upload_progress: Dict[str, Dict[str, Any]] = {}


def get_facebook_upload_progress(story_id: str) -> Dict[str, Any]:
    """Get the current Facebook upload status for a story."""
    return _fb_upload_progress.get(
        story_id,
        {"status": "idle", "progress": 0, "message": "Ready to upload to Facebook", "video_url": "", "error": ""},
    )


def set_facebook_upload_progress(story_id: str, data: Dict[str, Any]) -> None:
    """Update Facebook upload progress."""
    if story_id not in _fb_upload_progress:
        _fb_upload_progress[story_id] = {
            "status": "idle",
            "progress": 0,
            "message": "",
            "video_url": "",
            "video_id": "",
            "error": "",
        }
    _fb_upload_progress[story_id].update(data)


def get_instagram_upload_progress(story_id: str) -> Dict[str, Any]:
    """Get the current Instagram upload status for a story."""
    return _ig_upload_progress.get(
        story_id,
        {"status": "idle", "progress": 0, "message": "Ready to upload to Instagram", "post_url": "", "error": ""},
    )


def set_instagram_upload_progress(story_id: str, data: Dict[str, Any]) -> None:
    """Update Instagram upload progress."""
    if story_id not in _ig_upload_progress:
        _ig_upload_progress[story_id] = {
            "status": "idle",
            "progress": 0,
            "message": "",
            "post_url": "",
            "media_id": "",
            "error": "",
        }
    _ig_upload_progress[story_id].update(data)


def load_meta_credentials(credentials_path: Optional[Path] = None) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load Facebook and Instagram credentials from JSON file or environment variables.

    Returns:
        (fb_creds, ig_creds) where each is a dict of {"page_id": ..., "access_token": ...}
    """
    fb_creds: Dict[str, str] = {}
    ig_creds: Dict[str, str] = {}

    target_path = credentials_path or DEFAULT_CREDENTIALS_PATH
    if target_path.exists():
        try:
            data = json.loads(target_path.read_text(encoding="utf-8"))
            if "facebook" in data:
                fb_creds["page_id"] = data["facebook"].get("page_id", "").strip()
                fb_creds["access_token"] = data["facebook"].get("page_access_token", "").strip()
            if "instagram" in data:
                ig_creds["account_id"] = data["instagram"].get("account_id", "").strip()
                ig_creds["access_token"] = data["instagram"].get("access_token", "").strip()
        except Exception as e:
            logger.warning(f"Failed to parse {target_path}: {e}")

    # Fallback to environment variables
    if not fb_creds.get("page_id"):
        fb_creds["page_id"] = os.getenv("FB_PAGE_ID", "").strip()
    if not fb_creds.get("access_token"):
        fb_creds["access_token"] = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()

    if not ig_creds.get("account_id"):
        ig_creds["account_id"] = os.getenv("IG_ACCOUNT_ID", "").strip()
    if not ig_creds.get("access_token"):
        ig_creds["access_token"] = os.getenv("IG_ACCESS_TOKEN", "").strip() or fb_creds.get("access_token", "")

    # Auto-discover Instagram Account ID from connected Facebook Page if not explicitly provided
    if not ig_creds.get("account_id") and fb_creds.get("page_id") and ig_creds.get("access_token"):
        try:
            token = ig_creds.get("access_token")
            pid = fb_creds.get("page_id")
            disc_res = requests.get(
                f"{GRAPH_URL}/{pid}",
                params={"fields": "instagram_business_account{id,username}", "access_token": token},
                timeout=10,
            )
            if disc_res.ok:
                ig_biz = disc_res.json().get("instagram_business_account")
                if ig_biz and "id" in ig_biz:
                    discovered_id = str(ig_biz["id"]).strip()
                    ig_creds["account_id"] = discovered_id
                    logger.info(f"Auto-discovered Instagram Account ID: {discovered_id} (@{ig_biz.get('username', '')})")
        except Exception as disc_err:
            logger.debug(f"Instagram account auto-discovery note: {disc_err}")

    return fb_creds, ig_creds


def parse_metadata_for_social(metadata_path: Path) -> Dict[str, Any]:
    """Extract clean title, description, and hashtags suitable for Facebook and Instagram."""
    if not metadata_path.exists():
        return {
            "title": "Breaking News Update",
            "description": "Verified broadcast journalism dispatch.",
            "hashtags": ["#News", "#BreakingNews", "#DailyNews"],
            "caption": "Breaking News Update\n\nVerified broadcast journalism dispatch.\n\n#News #BreakingNews",
        }

    text = metadata_path.read_text(encoding="utf-8")

    title_match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Broadcast News Update"

    desc_match = re.search(r"^Description:\s*(.*?)(?=\n\[PLAYLISTS\]|\n\[AUDIENCE|\Z)", text, re.DOTALL | re.MULTILINE)
    description = desc_match.group(1).strip() if desc_match else ""

    tags_match = re.search(r"^Tags:\s*(.+)$", text, re.MULTILINE)
    tags_list = []
    if tags_match:
        for t in tags_match.group(1).split(","):
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', t.strip())
            if cleaned:
                tags_list.append(f"#{cleaned}")

    if not tags_list:
        tags_list = ["#News", "#BreakingNews", "#DailyNews", "#CurrentAffairs"]

    hashtags_str = " ".join(tags_list[:15])

    # Truncate clean caption for social feeds (Facebook allows 63,206 chars, Instagram allows 2,200 chars)
    # We create a structured, engaging social caption
    short_desc = description[:1400].strip() if len(description) > 1400 else description.strip()
    caption = f"{title}\n\n{short_desc}\n\n{hashtags_str}".strip()

    return {
        "title": title,
        "description": description,
        "hashtags": tags_list,
        "caption": caption,
    }


# =========================================================================
# 1. FACEBOOK PAGE VIDEO UPLOADER
# =========================================================================

def upload_video_to_facebook(
    video_path: Path,
    metadata_path: Optional[Path] = None,
    credentials_path: Optional[Path] = None,
    story_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload video directly to a Facebook Page via Meta Graph API v21.0 resumable upload protocol."""
    if not video_path.exists():
        err = f"Video file not found: {video_path}"
        logger.error(err)
        if story_id:
            set_facebook_upload_progress(story_id, {"status": "error", "error": err, "message": err})
        return {"status": "error", "message": err}

    fb_creds, _ = load_meta_credentials(credentials_path)
    page_id = fb_creds.get("page_id")
    access_token = fb_creds.get("access_token")

    if not page_id or not access_token:
        err = (
            "Facebook credentials not configured. Please add page_id and page_access_token "
            "to data/meta_credentials.json or set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN in .env. "
            "See META_API_SETUP_GUIDE.md for instructions."
        )
        logger.error(err)
        if story_id:
            set_facebook_upload_progress(story_id, {"status": "error", "error": err, "message": err})
        return {"status": "error", "message": err}

    meta = (
        parse_metadata_for_social(metadata_path)
        if metadata_path and metadata_path.exists()
        else {
            "title": video_path.stem.replace("_", " ").title(),
            "description": "Daily verified news dispatch.",
            "caption": f"{video_path.stem.replace('_', ' ').title()}\n\nDaily verified news dispatch.\n\n#News",
        }
    )

    file_size = video_path.stat().st_size
    thumbnail_path = video_path.parent / "thumbnail.jpg"

    if story_id:
        set_facebook_upload_progress(story_id, {
            "status": "initiating",
            "progress": 5,
            "message": f"Connecting to Facebook Graph API for Page {page_id}...",
        })

    logger.info(f"Initiating Facebook Page video upload for '{video_path.name}' ({round(file_size/(1024*1024), 1)} MB)...")

    session = requests.Session()

    try:
        # Phase 1: Initialize Resumable Upload
        init_res = session.post(
            f"{GRAPH_URL}/{page_id}/videos",
            data={
                "upload_phase": "start",
                "file_size": file_size,
                "access_token": access_token,
            },
            timeout=30,
        )
        init_data = init_res.json()

        if "error" in init_data:
            err_msg = init_data["error"].get("message", "Facebook API initialization failed")
            if "Session has expired" in err_msg or "Error validating access token" in err_msg:
                err_msg = (
                    "Your Facebook access token has expired (it was a temporary 1-hour session token). "
                    "Please generate a Never-Expiring Page Token using the Meta Access Token Debugger. "
                    "See instructions in META_API_SETUP_GUIDE.md."
                )
            elif "creative_folder_id" in err_msg:
                err_msg = (
                    f"ID '{page_id}' is a Business Portfolio ID, not a Facebook Page ID. "
                    "Please find your real Facebook Page ID on Facebook: Go to your Page -> About -> Page transparency -> Page ID."
                )
            raise RuntimeError(f"Facebook Graph API Error: {err_msg}")

        upload_session_id = init_data.get("upload_session_id")
        video_id = init_data.get("video_id")
        start_offset = int(init_data.get("start_offset", 0))
        end_offset = int(init_data.get("end_offset", file_size))

        logger.info(f"Facebook upload session initialized: {upload_session_id}")

        # Phase 2: Transfer Chunks
        chunk_size = 4 * 1024 * 1024  # 4 MB chunks
        with open(video_path, "rb") as vf:
            while start_offset < file_size:
                vf.seek(start_offset)
                current_chunk_size = min(chunk_size, file_size - start_offset)
                chunk_data = vf.read(current_chunk_size)

                pct = min(95, max(10, int((start_offset / file_size) * 100)))
                uploaded_mb = round(start_offset / (1024 * 1024), 1)
                total_mb = round(file_size / (1024 * 1024), 1)

                if story_id:
                    set_facebook_upload_progress(story_id, {
                        "status": "uploading",
                        "progress": pct,
                        "message": f"Uploading to Facebook: {pct}% ({uploaded_mb} MB / {total_mb} MB)",
                    })

                logger.info(f"Uploading Facebook video chunk {start_offset} - {start_offset + len(chunk_data)} ({pct}%)...")

                transfer_res = session.post(
                    f"{GRAPH_VIDEO_URL}/{page_id}/videos",
                    headers={"Authorization": f"OAuth {access_token}"},
                    data={
                        "upload_phase": "transfer",
                        "upload_session_id": upload_session_id,
                        "start_offset": str(start_offset),
                    },
                    files={"video_file_chunk": ("chunk.mp4", chunk_data, "video/mp4")},
                    timeout=90,
                )
                transfer_data = transfer_res.json()

                if "error" in transfer_data:
                    err_msg = transfer_data["error"].get("message", "Chunk transfer failed")
                    raise RuntimeError(f"Facebook Chunk Transfer Error: {err_msg}")

                next_start = int(transfer_data.get("start_offset", start_offset + len(chunk_data)))
                if next_start == start_offset:
                    # Guard against stuck offsets
                    start_offset += len(chunk_data)
                else:
                    start_offset = next_start

        # Phase 3: Finish & Publish
        if story_id:
            set_facebook_upload_progress(story_id, {
                "status": "publishing",
                "progress": 96,
                "message": "Finalizing Facebook video post & setting title/description...",
            })

        finish_data_payload = {
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "access_token": access_token,
            "title": meta["title"][:250],
            "description": meta["caption"][:5000],
            "published": "true",
        }

        files_payload = {}
        if thumbnail_path.exists():
            files_payload["thumb"] = ("thumbnail.jpg", open(thumbnail_path, "rb"), "image/jpeg")

        finish_res = session.post(
            f"{GRAPH_URL}/{page_id}/videos",
            data=finish_data_payload,
            files=files_payload if files_payload else None,
            timeout=45,
        )
        finish_json = finish_res.json()

        if files_payload and "thumb" in files_payload:
            try:
                files_payload["thumb"][1].close()
            except Exception:
                pass

        if "error" in finish_json:
            err_msg = finish_json["error"].get("message", "Finishing Facebook video failed")
            raise RuntimeError(f"Facebook Finish Error: {err_msg}")

        published_video_id = finish_json.get("id", video_id or "unknown")
        fb_video_url = f"https://www.facebook.com/{page_id}/videos/{published_video_id}"

        logger.info(f"Video uploaded to Facebook Page successfully! Post URL: {fb_video_url}")

        if story_id:
            set_facebook_upload_progress(story_id, {
                "status": "completed",
                "progress": 100,
                "video_id": published_video_id,
                "video_url": fb_video_url,
                "message": f"Successfully published to Facebook Page! ID: {published_video_id}",
            })

        return {
            "status": "success",
            "platform": "facebook",
            "video_id": published_video_id,
            "video_url": fb_video_url,
            "message": "Successfully published to Facebook Page.",
        }

    except Exception as e:
        err_str = str(e)
        logger.error(f"Facebook upload failed: {err_str}", exc_info=True)
        if story_id:
            set_facebook_upload_progress(story_id, {
                "status": "error",
                "error": err_str,
                "message": f"Facebook upload error: {err_str}",
            })
        return {"status": "error", "message": err_str}


# =========================================================================
# 2. INSTAGRAM REELS / VIDEO UPLOADER
# =========================================================================

def upload_video_to_instagram(
    video_path: Path,
    metadata_path: Optional[Path] = None,
    credentials_path: Optional[Path] = None,
    story_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload video directly to Instagram Professional/Creator account via Instagram Graph API resumable container protocol."""
    if not video_path.exists():
        err = f"Video file not found: {video_path}"
        logger.error(err)
        if story_id:
            set_instagram_upload_progress(story_id, {"status": "error", "error": err, "message": err})
        return {"status": "error", "message": err}

    _, ig_creds = load_meta_credentials(credentials_path)
    account_id = ig_creds.get("account_id")
    access_token = ig_creds.get("access_token")

    if not account_id or not access_token:
        err = (
            "Instagram credentials not configured. Please add account_id and access_token "
            "to data/meta_credentials.json or set IG_ACCOUNT_ID and IG_ACCESS_TOKEN in .env. "
            "See META_API_SETUP_GUIDE.md for instructions."
        )
        logger.error(err)
        if story_id:
            set_instagram_upload_progress(story_id, {"status": "error", "error": err, "message": err})
        return {"status": "error", "message": err}

    if access_token.startswith("IGAA") or access_token.startswith("IGQV"):
        err = (
            "The IG_ACCESS_TOKEN in your .env starts with 'IGAA' (Instagram Login token), which cannot upload video files directly from your PC. "
            "Please use the same Meta Page Access Token (starts with 'EAA') that has 'instagram_content_publish' and 'instagram_basic' permissions. "
            "Set IG_ACCESS_TOKEN equal to your FB_PAGE_ACCESS_TOKEN in .env."
        )
        logger.error(err)
        if story_id:
            set_instagram_upload_progress(story_id, {"status": "error", "error": err, "message": err})
        return {"status": "error", "message": err}

    meta = (
        parse_metadata_for_social(metadata_path)
        if metadata_path and metadata_path.exists()
        else {
            "title": video_path.stem.replace("_", " ").title(),
            "caption": f"{video_path.stem.replace('_', ' ').title()}\n\nVerified broadcast news dispatch.\n\n#News #DailyNews",
        }
    )

    file_size = video_path.stat().st_size
    thumbnail_path = video_path.parent / "thumbnail.jpg"

    if story_id:
        set_instagram_upload_progress(story_id, {
            "status": "initiating",
            "progress": 5,
            "message": f"Initializing Instagram Media Container for account {account_id}...",
        })

    logger.info(f"Initiating Instagram video container creation for '{video_path.name}' ({round(file_size/(1024*1024), 1)} MB)...")

    session = requests.Session()

    try:
        # Phase 1: Initialize Resumable Container on Instagram
        init_res = session.post(
            f"{GRAPH_URL}/{account_id}/media",
            data={
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": meta["caption"][:2150],  # Instagram caption max 2200 chars
                "access_token": access_token,
            },
            timeout=30,
        )
        init_data = init_res.json()

        if "error" in init_data:
            err_msg = init_data["error"].get("message", "Instagram container creation failed")
            raise RuntimeError(f"Instagram Graph API Error: {err_msg}")

        container_id = init_data.get("id")
        upload_uri = init_data.get("uri")

        if not upload_uri:
            raise RuntimeError(f"Instagram did not return a valid upload URI. Response: {init_data}")

        logger.info(f"Instagram container created: {container_id}, upload URI received.")

        # Phase 2: Stream Video Bytes to Instagram Rupload URI
        if story_id:
            set_instagram_upload_progress(story_id, {
                "status": "uploading",
                "progress": 20,
                "message": "Streaming video bytes directly to Instagram secure endpoint...",
            })

        with open(video_path, "rb") as vf:
            video_bytes = vf.read()

        rupload_headers = {
            "Authorization": f"OAuth {access_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        }

        stream_res = session.post(
            upload_uri,
            headers=rupload_headers,
            data=video_bytes,
            timeout=180,
        )
        stream_data = stream_res.json() if stream_res.content else {}

        if "error" in stream_data:
            err_msg = stream_data["error"].get("message", "Instagram video byte upload failed")
            raise RuntimeError(f"Instagram Stream Error: {err_msg}")

        logger.info(f"Instagram bytes uploaded successfully. Waiting for container encoding...")

        # Phase 3: Poll Instagram Container Processing Status
        max_attempts = 30  # Wait up to ~90 seconds for video encoding on Meta servers
        container_ready = False

        for attempt in range(max_attempts):
            pct = min(92, 50 + int((attempt / max_attempts) * 40))
            if story_id:
                set_instagram_upload_progress(story_id, {
                    "status": "processing",
                    "progress": pct,
                    "message": f"Instagram is processing video container (attempt {attempt + 1}/{max_attempts})...",
                })

            time.sleep(3)

            status_res = session.get(
                f"{GRAPH_URL}/{container_id}",
                params={"fields": "status_code,status", "access_token": access_token},
                timeout=20,
            )
            status_data = status_res.json()
            code = status_data.get("status_code", "").upper()

            if code == "FINISHED":
                container_ready = True
                logger.info(f"Instagram container {container_id} processing completed successfully.")
                break
            elif code == "ERROR":
                err_detail = status_data.get("status", "Unknown Instagram processing error")
                raise RuntimeError(f"Instagram container processing failed: {err_detail}")
            else:
                logger.debug(f"Instagram container {container_id} status: {code} ({status_data.get('status', '')})")

        if not container_ready:
            raise TimeoutError("Timed out waiting for Instagram to process the video container.")

        # Phase 4: Publish Instagram Media Container
        if story_id:
            set_instagram_upload_progress(story_id, {
                "status": "publishing",
                "progress": 95,
                "message": "Publishing video to your Instagram feed...",
            })

        publish_res = session.post(
            f"{GRAPH_URL}/{account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": access_token,
            },
            timeout=40,
        )
        publish_data = publish_res.json()

        if "error" in publish_data:
            err_msg = publish_data["error"].get("message", "Instagram media publish failed")
            raise RuntimeError(f"Instagram Publish Error: {err_msg}")

        ig_media_id = publish_data.get("id")

        # Fetch permalink if available
        post_url = f"https://www.instagram.com/"
        try:
            permalink_res = session.get(
                f"{GRAPH_URL}/{ig_media_id}",
                params={"fields": "permalink", "access_token": access_token},
                timeout=15,
            )
            permalink_data = permalink_res.json()
            if "permalink" in permalink_data:
                post_url = permalink_data["permalink"]
        except Exception:
            pass

        logger.info(f"Video successfully published to Instagram! Media ID: {ig_media_id}, Link: {post_url}")

        if story_id:
            set_instagram_upload_progress(story_id, {
                "status": "completed",
                "progress": 100,
                "media_id": ig_media_id,
                "post_url": post_url,
                "message": f"Successfully published to Instagram! Media ID: {ig_media_id}",
            })

        return {
            "status": "success",
            "platform": "instagram",
            "media_id": ig_media_id,
            "post_url": post_url,
            "message": "Successfully published to Instagram.",
        }

    except Exception as e:
        err_str = str(e)
        logger.error(f"Instagram upload failed: {err_str}", exc_info=True)
        if story_id:
            set_instagram_upload_progress(story_id, {
                "status": "error",
                "error": err_str,
                "message": f"Instagram upload error: {err_str}",
            })
        return {"status": "error", "message": err_str}
