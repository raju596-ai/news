"""Automated Daily Scheduler for AI News Video Generation & YouTube Publishing.

Production-grade, zero-human-interaction autonomous runner:
- Default execution times: 08:30 AM & 05:00 PM (Local Time).
- Generates curated 5-minute broadcast news videos.
- Automatically publishes to YouTube with SEO metadata, tags, and custom thumbnails.
- Self-healing with automatic retries, rotating logs, and JSON state persistence.
- Supports both:
    1. Continuous background daemon loop (`python -m news.scheduler`)
    2. One-shot execution for Windows Task Scheduler (`python -m news.scheduler --now`)
"""

import sys
import os
import time
import json
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news.config import settings, ROOT_DIR
from news.agents.orchestrator import OrchestratorAgent
from news.agents.base import NewsStory
from news.tools.youtube_uploader import check_youtube_auth_status, upload_video_to_youtube

# Set up robust rotating log handler
log_file = ROOT_DIR / "scheduler.log"
handler = RotatingFileHandler(
    log_file,
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=3,
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logger = logging.getLogger("NewsScheduler")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.addHandler(stream_handler)

STATUS_FILE = settings.STORAGE_DIR / "scheduler_status.json"

# Default daily slots: 08:30 AM and 05:00 PM local time
def parse_scheduled_times() -> List[Tuple[int, int]]:
    """Parse scheduled run times from environment or defaults (08:30 AM & 05:00 PM)."""
    t1 = os.getenv("SCHEDULE_TIME_MORNING", "08:30").strip()
    t2 = os.getenv("SCHEDULE_TIME_EVENING", "17:00").strip()
    times = []
    for t_str in [t1, t2]:
        try:
            parts = t_str.split(":")
            times.append((int(parts[0]), int(parts[1])))
        except Exception:
            pass
    return times or [(8, 30), (17, 0)]


SCHEDULED_TIMES = parse_scheduled_times()


def get_seconds_until_next_run() -> Tuple[float, str, datetime]:
    """Calculate seconds until the next scheduled slot."""
    now = datetime.now()
    candidates = []

    for hour, minute in SCHEDULED_TIMES:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            # Slot for today already passed, schedule for tomorrow
            target += timedelta(days=1)
        candidates.append(target)

    next_slot = min(candidates)
    delta_seconds = (next_slot - now).total_seconds()
    return delta_seconds, next_slot.strftime("%Y-%m-%d %I:%M %p"), next_slot


def save_scheduler_status(
    status: str,
    edition: str,
    videos_uploaded: List[Dict[str, Any]],
    error: str = None,
    next_run: str = None,
):
    """Persist current automation state to storage/scheduler_status.json."""
    try:
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "last_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "last_run_local": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "edition": edition,
            "status": status,
            "videos_uploaded_count": len(videos_uploaded),
            "videos_uploaded": videos_uploaded,
            "next_scheduled_run": next_run or get_seconds_until_next_run()[1],
            "last_error": error,
        }
        STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not save scheduler status: {e}")


def get_scheduler_status() -> Dict[str, Any]:
    """Read current scheduler state from file."""
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    _, next_run_str, _ = get_seconds_until_next_run()
    return {
        "status": "idle",
        "last_run_local": "Never",
        "edition": "None",
        "videos_uploaded_count": 0,
        "videos_uploaded": [],
        "next_scheduled_run": next_run_str,
        "last_error": None,
    }


async def run_news_cycle(edition_name: str = "Automated Edition", max_uploads_per_run: int = 2) -> Dict[str, Any]:
    """Execute end-to-end autonomous news generation and YouTube publishing.

    Args:
        edition_name: Human-friendly name for this run (e.g. Morning Edition).
        max_uploads_per_run: Number of videos to publish (1-2 per edition stays well within YouTube's 10k quota).
    """
    logger.info("=" * 80)
    logger.info(f"STARTING PRODUCTION NEWS CYCLE: {edition_name}")
    logger.info("=" * 80)

    start_time = time.time()
    uploaded_records: List[Dict[str, Any]] = []
    orchestrator = OrchestratorAgent()

    try:
        # 1. Run full 6-agent news pipeline
        logger.info("[PIPELINE STEP 1/2] Discovering, scripting, rendering 1080p news videos...")
        world_stories, india_stories = await orchestrator.run_full_pipeline(auto_render_videos=True)

        # Select Top 1 World + Top 1 India (or top stories up to max_uploads_per_run)
        curated_candidates: List[NewsStory] = []
        if world_stories:
            curated_candidates.append(world_stories[0])
        if india_stories:
            curated_candidates.append(india_stories[0])

        # If more slots allowed, append remaining
        remaining = [s for s in world_stories[1:] + india_stories[1:] if s not in curated_candidates]
        curated_candidates.extend(remaining[:max(0, max_uploads_per_run - len(curated_candidates))])

        logger.info(f"Curated {len(curated_candidates)} high-priority broadcast stories for publishing.")

        # 2. Check YouTube credentials
        auth_status = check_youtube_auth_status()
        can_upload = auth_status.get("authenticated") or auth_status.get("client_secret_configured")

        if not can_upload:
            logger.warning("[YOUTUBE STEP] YouTube credentials not configured. Videos rendered and saved locally in storage/media.")
            save_scheduler_status(
                status="saved_locally",
                edition=edition_name,
                videos_uploaded=[],
                error="YouTube not authenticated. Run auth_youtube.bat to link your channel.",
            )
            return {"status": "saved_locally", "uploaded": []}

        # 3. Publish to YouTube with retry handling
        logger.info("[PIPELINE STEP 2/2] Publishing rendered videos directly to YouTube...")
        for rank_idx, story in enumerate(curated_candidates, 1):
            video_path = None
            if story.media.video_path and Path(story.media.video_path).exists():
                video_path = Path(story.media.video_path)
            else:
                candidate = settings.MEDIA_DIR / story.id / "final_news_video.mp4"
                if candidate.exists():
                    video_path = candidate

            if not video_path:
                logger.warning(f"Skipping story '{story.title}' — final MP4 video file not found.")
                continue

            metadata_path = video_path.parent / "metadata.txt"
            upload_success = False

            # Attempt upload with 1 retry
            for attempt in range(2):
                try:
                    logger.info(f"Publishing Story #{rank_idx} to YouTube: '{story.title}' (Attempt {attempt + 1})...")
                    res = await asyncio.to_thread(
                        upload_video_to_youtube,
                        video_path=video_path,
                        metadata_path=metadata_path if metadata_path.exists() else None,
                        story_id=story.id,
                        rank=rank_idx,
                    )
                    v_url = res.get("video_url")
                    v_id = res.get("video_id")
                    schedule_desc = res.get("schedule_description", "Published")

                    logger.info(f"[SUCCESS] Uploaded '{story.title}' -> {v_url} ({schedule_desc})")
                    uploaded_records.append({
                        "story_id": story.id,
                        "title": story.title,
                        "region": story.region.value,
                        "video_url": v_url,
                        "video_id": v_id,
                        "schedule": schedule_desc,
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    })
                    upload_success = True
                    break
                except Exception as up_err:
                    err_msg = str(up_err)
                    logger.error(f"[UPLOAD ERROR] Attempt {attempt + 1} failed for '{story.title}': {err_msg}")
                    if "invalid_grant" in err_msg or "expired" in err_msg.lower():
                        logger.error("CRITICAL: YouTube OAuth token has expired or was revoked. Please run: auth_youtube.bat")
                        break
                    if attempt == 0:
                        logger.info("Waiting 30 seconds before retrying upload...")
                        await asyncio.sleep(30)

        # 4. Housekeeping: prune old media cache older than 14 days to free disk space
        try:
            from news.tools.maintenance import prune_old_media_cache
            pruned = prune_old_media_cache(max_age_days=14)
            if pruned > 0:
                logger.info(f"Housekeeping: Pruned {pruned} expired media directories.")
        except Exception as maint_err:
            logger.debug(f"Housekeeping note: {maint_err}")

        elapsed_min = (time.time() - start_time) / 60
        logger.info(f"=== {edition_name} FINISHED in {elapsed_min:.1f} minutes. Uploaded: {len(uploaded_records)} videos ===")

        final_status = "success" if uploaded_records else "partial"
        save_scheduler_status(
            status=final_status,
            edition=edition_name,
            videos_uploaded=uploaded_records,
            error=None if uploaded_records else "No videos uploaded during run",
        )
        return {"status": final_status, "uploaded": uploaded_records}

    except Exception as cycle_err:
        logger.error(f"FATAL ERROR in {edition_name}: {cycle_err}", exc_info=True)
        save_scheduler_status(
            status="failed",
            edition=edition_name,
            videos_uploaded=uploaded_records,
            error=str(cycle_err),
        )
        return {"status": "failed", "error": str(cycle_err)}


async def scheduler_loop():
    """Continuous background daemon loop running autonomously twice a day."""
    logger.info("=" * 80)
    logger.info("NEWSINTEL AUTONOMOUS DAILY SCHEDULER STARTED")
    logger.info(f"Slots Configured: {', '.join([f'{h:02d}:{m:02d}' for h, m in SCHEDULED_TIMES])} (Local Time)")
    logger.info("=" * 80)

    while True:
        try:
            wait_seconds, next_run_str, target_dt = get_seconds_until_next_run()
            logger.info(f"Next automated cycle: {next_run_str} (in {wait_seconds / 3600:.2f} hours)")

            # Update status file with next run
            current_status = get_scheduler_status()
            current_status["next_scheduled_run"] = next_run_str
            STATUS_FILE.write_text(json.dumps(current_status, indent=2), encoding="utf-8")

            # Sleep until scheduled time
            await asyncio.sleep(wait_seconds)

            # Determine edition name
            now = datetime.now()
            slot_name = "Morning Edition (08:30 AM)" if now.hour < 12 else "Evening Edition (05:00 PM)"
            await run_news_cycle(slot_name)

            # Short cooldown to avoid triggering multiple times within the same minute
            await asyncio.sleep(70)

        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled.")
            break
        except Exception as loop_err:
            logger.error(f"Unexpected error in scheduler loop: {loop_err}", exc_info=True)
            await asyncio.sleep(60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NewsIntel Autonomous Daily Video Generator & YouTube Publisher")
    parser.add_argument("--now", action="store_true", help="Execute a full cycle immediately, then exit (ideal for Windows Task Scheduler)")
    parser.add_argument("--daemon", action="store_true", help="Run the continuous 24/7 background scheduler loop")
    parser.add_argument("--edition", type=str, default="On-Demand Edition", help="Label for this execution")
    args = parser.parse_args()

    if args.now:
        logger.info(f"Triggering immediate news cycle: {args.edition}")
        asyncio.run(run_news_cycle(args.edition))
    else:
        # Default behavior: continuous autonomous scheduler
        try:
            asyncio.run(scheduler_loop())
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
