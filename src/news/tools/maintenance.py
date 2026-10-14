"""Automated Storage & Cache Maintenance Utility.
Prunes intermediate temporary WAVs, TS chunks, and working clips after video assembly,
and cleans up historical media archives older than the retention threshold.
"""

import time
import shutil
import logging
from pathlib import Path
from typing import List
from ..config import settings

logger = logging.getLogger(__name__)


def cleanup_story_intermediates(story_id: str) -> int:
    """Clean temporary scratch files for a story after video assembly.
    Retains final video, named video, thumbnail, metadata.txt, and rendered slide graphics.
    Returns bytes freed.
    """
    story_dir = settings.MEDIA_DIR / story_id
    if not story_dir.exists():
        return 0

    freed_bytes = 0

    # 1. Intermediate uncompressed audio files and temp files
    intermediate_files: List[Path] = [
        story_dir / "master_broadcast_audio.wav",
        story_dir / "body_news_video.mp4",
        story_dir / "slides_concat.txt",
        story_dir / "clips_concat.txt",
        story_dir / "stream_list.txt",
        story_dir / "final_news_video_stream_list.txt",
    ]

    # Also match any .tmp files or .txt concat files
    for p in story_dir.glob("*.tmp*"):
        intermediate_files.append(p)

    for f in intermediate_files:
        if f.exists() and f.is_file():
            try:
                sz = f.stat().st_size
                f.unlink()
                freed_bytes += sz
                logger.debug(f"Pruned scratch file: {f.name} ({sz} bytes)")
            except Exception as e:
                logger.debug(f"Could not delete scratch file {f.name}: {e}")

    # 2. Intermediate video_clips folder (individual scene mp4s merged into final video)
    clips_dir = story_dir / "video_clips"
    if clips_dir.exists() and clips_dir.is_dir():
        try:
            for cp in clips_dir.glob("*.mp4"):
                freed_bytes += cp.stat().st_size
            shutil.rmtree(clips_dir)
            logger.debug(f"Pruned intermediate video_clips directory for story {story_id}")
        except Exception as e:
            logger.debug(f"Could not remove clips_dir: {e}")

    logger.info(f"Storage Maintenance: Cleaned scratch files for story {story_id} ({freed_bytes / (1024 * 1024):.1f} MB freed)")
    return freed_bytes


def prune_old_media_cache(max_age_days: int = 14) -> int:
    """Remove historical story directories older than max_age_days. Returns count of pruned stories."""
    media_dir = settings.MEDIA_DIR
    if not media_dir.exists():
        return 0

    now = time.time()
    cutoff_sec = max_age_days * 86400
    pruned_count = 0

    for story_folder in media_dir.iterdir():
        if story_folder.is_dir():
            try:
                folder_mtime = story_folder.stat().st_mtime
                if (now - folder_mtime) > cutoff_sec:
                    shutil.rmtree(story_folder)
                    pruned_count += 1
                    logger.info(f"Storage Maintenance: Pruned expired story archive: {story_folder.name} (> {max_age_days} days old)")
            except Exception as e:
                logger.warning(f"Storage Maintenance: Could not prune folder {story_folder.name}: {e}")

    return pruned_count
