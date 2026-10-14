"""Hardware-accelerated video encoding and fast stream-copy normalization utilities."""

import os
import logging
import subprocess
from pathlib import Path
from typing import Tuple, List, Optional
from ..config import settings

logger = logging.getLogger(__name__)

# Cached encoder configuration
_DETECTED_ENCODER_INFO: Optional[Tuple[str, List[str], str]] = None


def get_best_video_encoder() -> Tuple[str, List[str], str]:
    """Detect the fastest working H.264 video encoder on the system:
    1. Intel QuickSync (h264_qsv) — Hardware accelerated, 5-8x faster than CPU.
    2. Windows Media Foundation (h264_mf) — Windows GPU encoder.
    3. libx264 — Software fallback (CPU).

    Returns:
        (encoder_name, encoding_arguments, pixel_format_filter)
    """
    global _DETECTED_ENCODER_INFO
    if _DETECTED_ENCODER_INFO is not None:
        return _DETECTED_ENCODER_INFO

    ffmpeg_path = settings.FFMPEG_PATH

    # Test 1: Intel QuickSync (h264_qsv)
    try:
        cmd_qsv = [
            ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", "nullsrc=s=1920x1080:d=1",
            "-vf", "format=nv12",
            "-c:v", "h264_qsv",
            "-global_quality", "23",
            "-f", "null", "-",
        ]
        res = subprocess.run(cmd_qsv, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            logger.info("Hardware Acceleration: Detected active Intel QuickSync (h264_qsv)!")
            _DETECTED_ENCODER_INFO = ("h264_qsv", ["-c:v", "h264_qsv", "-global_quality", "23"], "format=nv12")
            return _DETECTED_ENCODER_INFO
    except Exception as e:
        logger.debug(f"h264_qsv probe note: {e}")

    # Test 2: Windows Media Foundation (h264_mf)
    try:
        cmd_mf = [
            ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", "nullsrc=s=1920x1080:d=1",
            "-vf", "format=nv12",
            "-c:v", "h264_mf",
            "-b:v", "4500k",
            "-f", "null", "-",
        ]
        res = subprocess.run(cmd_mf, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            logger.info("Hardware Acceleration: Detected active Windows Media Foundation (h264_mf)!")
            _DETECTED_ENCODER_INFO = ("h264_mf", ["-c:v", "h264_mf", "-b:v", "4500k"], "format=nv12")
            return _DETECTED_ENCODER_INFO
    except Exception as e:
        logger.debug(f"h264_mf probe note: {e}")

    # Fallback: CPU libx264
    logger.info("Hardware Acceleration: Defaulting to CPU software encoding (libx264)")
    _DETECTED_ENCODER_INFO = ("libx264", ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast"], "format=yuv420p")
    return _DETECTED_ENCODER_INFO


def get_or_create_normalized_clip(clip_path: Path | str) -> Path:
    """Pre-normalizes intro (start.mp4) or outro (end.mp4) once on disk to standard parameters:
    1920x1080, 30 FPS, yuv420p, AAC 48kHz stereo.
    Allows instant stream-copy concatenation (-c copy in < 1 second).
    """
    clip_path = Path(clip_path)
    if not clip_path.exists():
        return clip_path

    normalized_path = clip_path.parent / f"{clip_path.stem}_normalized.mp4"
    if normalized_path.exists() and normalized_path.stat().st_mtime >= clip_path.stat().st_mtime:
        return normalized_path

    logger.info(f"Normalizing '{clip_path.name}' once for instant stream-copy concatenation...")
    cmd = [
        settings.FFMPEG_PATH,
        "-y",
        "-i", str(clip_path.resolve()),
        "-vf", f"scale={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-r", str(settings.VIDEO_FPS),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-ar", str(settings.AUDIO_SAMPLE_RATE),
        "-ac", "2",
        "-b:a", settings.AUDIO_BITRATE,
        "-movflags", "+faststart",
        str(normalized_path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and normalized_path.exists():
            logger.info(f"Successfully normalized '{clip_path.name}' -> '{normalized_path.name}' ({normalized_path.stat().st_size} bytes)")
            return normalized_path
    except Exception as e:
        logger.warning(f"Clip normalization error: {e}")

    return clip_path
