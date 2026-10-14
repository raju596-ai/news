"""Automated Daily Scheduler for AI News Video Generation & YouTube Publishing.

Runs automatically at:
- 08:30 AM (Morning News Edition)
- 05:00 PM (Evening News Edition)

Selects Top 2 World + Top 2 India stories, renders full 5-minute broadcast videos,
and publishes them to YouTube.
"""

import sys
import os
import time
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news.config import settings, ROOT_DIR
from news.agents.orchestrator import OrchestratorAgent
from news.tools.youtube_uploader import check_youtube_auth_status, upload_video_to_youtube

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT_DIR / "scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("NewsScheduler")

SCHEDULED_TIMES = [
    (8, 30),   # 08:30 AM
    (17, 0),   # 05:00 PM (17:00)
]


def get_seconds_until_next_run() -> tuple[float, str]:
    """Calculate seconds until the next scheduled slot (08:30 AM or 05:00 PM)."""
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
    return delta_seconds, next_slot.strftime("%Y-%m-%d %I:%M %p")


async def run_news_cycle(edition_name: str = "Automated Edition"):
    """Execute end-to-end news video generation and optional YouTube upload."""
    logger.info(f"=== Starting {edition_name} News Video Pipeline ===")
    orchestrator = OrchestratorAgent()

    try:
        world_stories, india_stories = await orchestrator.run_full_pipeline(auto_render_videos=True)
        all_stories = world_stories + india_stories
        logger.info(f"Generated {len(all_stories)} total broadcast news stories.")

        # Check YouTube credentials
        auth_status = check_youtube_auth_status()
        can_upload = auth_status["authenticated"] or auth_status["client_secret_configured"]

        if can_upload:
            logger.info("YouTube integration configured. Initiating upload for rendered videos...")
            for story in all_stories:
                if story.media.video_path and Path(story.media.video_path).exists():
                    video_file = Path(story.media.video_path)
                    meta_file = video_file.parent / "metadata.txt"
                    try:
                        logger.info(f"Uploading '{story.title}' to YouTube...")
                        res = await asyncio.to_thread(
                            upload_video_to_youtube,
                            video_path=video_file,
                            metadata_path=meta_file if meta_file.exists() else None,
                        )
                        logger.info(f"[SUCCESS] Uploaded '{story.title}' -> {res.get('video_url')}")
                    except Exception as up_err:
                        logger.error(f"[ERROR] Failed to upload '{story.title}': {up_err}")
        else:
            logger.info("YouTube client_secret.json / token not configured yet. Videos saved locally.")

        # Housekeeping: prune historical media archives older than 14 days
        try:
            from news.tools.maintenance import prune_old_media_cache
            pruned = prune_old_media_cache(max_age_days=14)
            if pruned > 0:
                logger.info(f"Scheduler Housekeeping: Pruned {pruned} expired media directories.")
        except Exception as maint_err:
            logger.debug(f"Housekeeping note: {maint_err}")

    except Exception as e:
        logger.error(f"Error during {edition_name}: {e}", exc_info=True)


async def scheduler_loop():
    """Continuous scheduler loop running at 08:30 AM and 05:00 PM daily."""
    logger.info("NewsIntel Automated Scheduler initialized.")
    logger.info("Scheduled Daily Slots: 08:30 AM & 05:00 PM (Local Time).")

    while True:
        wait_seconds, next_run_time_str = get_seconds_until_next_run()
        logger.info(f"Next automated run scheduled for: {next_run_time_str} (in {wait_seconds / 3600:.2f} hours)")

        # Wait until scheduled time
        await asyncio.sleep(wait_seconds)

        now = datetime.now()
        slot_label = "Morning Edition (8:30 AM)" if now.hour < 12 else "Evening Edition (5:00 PM)"
        await run_news_cycle(slot_label)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI News Video Automated Scheduler")
    parser.add_argument("--now", action="store_true", help="Run a full news cycle immediately, then enter schedule loop")
    args = parser.parse_args()

    async def _start():
        if args.now:
            logger.info("Running immediate on-demand news cycle (--now flag detected)...")
            await run_news_cycle("Immediate On-Demand Edition")
        await scheduler_loop()

    try:
        asyncio.run(_start())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
