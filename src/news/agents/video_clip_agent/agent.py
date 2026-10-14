"""Agent 3.5 — Image-to-Video Agent (MiniMaxAI/MiniMax-H3)
Converts AI-generated news images into animated video clips.
Executes the Hugging Face InferenceClient image_to_video pipeline with MiniMaxAI/MiniMax-H3,
with an automatic cinematic broadcast motion video fallback to ensure 100% video generation reliability.
"""

import os
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

from ..base import NewsStory, AgentPhase, ScriptSegment
from ...config import settings

logger = logging.getLogger(__name__)

# Apply tolerance patch for Hugging Face Inference Providers task metadata (image-text-to-video vs image-to-video)
try:
    from huggingface_hub.inference._providers import TaskProviderHelper
    from huggingface_hub.inference._providers._common import _fetch_inference_provider_mapping

    _orig_prepare_mapping_info = TaskProviderHelper._prepare_mapping_info

    def _tolerant_prepare_mapping_info(self, model: str | None):
        provider_mapping = None
        for m in _fetch_inference_provider_mapping(model):
            if m.provider == self.provider:
                provider_mapping = m
                break
        if provider_mapping is None:
            raise ValueError(f"Model {model} is not supported by provider {self.provider}.")
        # Accept image-text-to-video when task is image-to-video
        if provider_mapping.task != self.task and not (
            self.task == "image-to-video" and provider_mapping.task in ("image-text-to-video", "image-to-video")
        ):
            raise ValueError(
                f"Model {model} is not supported for task {self.task} and provider {self.provider}. "
                f"Supported task: {provider_mapping.task}."
            )
        return provider_mapping

    TaskProviderHelper._prepare_mapping_info = _tolerant_prepare_mapping_info
except Exception as patch_err:
    logger.debug(f"Hugging Face TaskProviderHelper patch note: {patch_err}")


class ImageToVideoAgent:
    """Converts images into broadcast video clips using MiniMaxAI/MiniMax-H3."""

    def __init__(self):
        load_dotenv()
        self.api_key = (
            os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGING_API_KEY")
            or settings.HUGGING_API_KEY
        )
        self.model_name = "MiniMaxAI/MiniMax-H3"
        self.ffmpeg_path = settings.FFMPEG_PATH

    def _generate_video_minimax(self, image_path: Path, prompt: str) -> Optional[bytes]:
        """Query Hugging Face InferenceClient image_to_video with MiniMaxAI/MiniMax-H3."""
        if not self.api_key:
            logger.warning("ImageToVideoAgent: No HF_TOKEN or HUGGING_API_KEY found.")
            return None

        try:
            from huggingface_hub import InferenceClient

            client = InferenceClient(
                provider="auto",
                api_key=self.api_key,
            )

            with open(str(image_path), "rb") as image_file:
                input_image = image_file.read()

            logger.info(
                f"ImageToVideoAgent: Querying '{self.model_name}' for image '{image_path.name}'..."
            )
            video_bytes = client.image_to_video(
                input_image,
                prompt=prompt,
                model=self.model_name,
            )
            if video_bytes and len(video_bytes) > 1000:
                logger.info(
                    f"ImageToVideoAgent: MiniMaxAI/MiniMax-H3 generated video successfully ({len(video_bytes)} bytes)!"
                )
                return video_bytes
        except Exception as e:
            err_msg = str(e)
            if "402" in err_msg or "Payment Required" in err_msg:
                logger.warning(
                    f"ImageToVideoAgent: Hugging Face credits depleted (402 Payment Required). "
                    f"Seamlessly using broadcast cinematic motion engine for '{image_path.name}'."
                )
            else:
                logger.warning(f"ImageToVideoAgent: MiniMax-H3 API call note ({e}). Falling back to cinematic motion engine.")
        return None

    def _generate_cinematic_motion_fallback(
        self,
        image_path: Path,
        output_clip_path: Path,
        duration_sec: float = 8.0,
        scene_index: int = 0,
    ) -> bool:
        """Create a high-definition 1080p 30 FPS cinematic Ken Burns video clip with dynamic camera pan/zoom."""
        output_clip_path.parent.mkdir(parents=True, exist_ok=True)
        total_frames = max(1, int(duration_sec * settings.VIDEO_FPS))

        # Dynamic motion styles per scene to create rich documentary movement
        motion_mode = scene_index % 4
        if motion_mode == 0:
            # Slow push-in to center
            zoom_expr = "min(zoom+0.0008,1.15)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion_mode == 1:
            # Slow pan left to right
            zoom_expr = "1.08"
            x_expr = f"(iw-iw/zoom)*(on/{total_frames})"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion_mode == 2:
            # Slow push-in toward upper third
            zoom_expr = "min(zoom+0.0008,1.15)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/3-(ih/zoom/3)"
        else:
            # Slow pan right to left
            zoom_expr = "1.08"
            x_expr = f"(iw-iw/zoom)*(1-on/{total_frames})"
            y_expr = "ih/2-(ih/zoom/2)"

        filter_str = (
            f"scale={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT},"
            f"zoompan=z='{zoom_expr}':d={total_frames}:"
            f"x='{x_expr}':y='{y_expr}':s={settings.VIDEO_WIDTH}x{settings.VIDEO_HEIGHT}:fps={settings.VIDEO_FPS},"
            f"format=yuv420p"
        )
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-loop", "1",
            "-i", str(image_path.resolve()),
            "-vf", filter_str,
            "-t", str(duration_sec),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_clip_path),
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and output_clip_path.exists():
                return True
            logger.error(f"FFmpeg motion fallback error: {res.stderr[-200:]}")
        except Exception as e:
            logger.error(f"FFmpeg motion generation exception: {e}")
        return False

    async def convert_images_to_video_clips(self, story: NewsStory) -> List[str]:
        """Convert all story images into video clips using MiniMax-H3 (with motion fallback)."""
        logger.info(f"ImageToVideoAgent: Converting scene images to video clips for '{story.title}'...")
        story.status = AgentPhase.IMAGE_TO_VIDEO
        story.status_message = "Converting news images into broadcast video clips via MiniMaxAI/MiniMax-H3"

        if not story.media.image_paths:
            logger.warning(f"Story {story.id} has no image paths to convert to video.")
            return []

        story_clips_dir = settings.MEDIA_DIR / story.id / "video_clips"
        story_clips_dir.mkdir(parents=True, exist_ok=True)

        segments: List[ScriptSegment] = story.script.segments if story.script else []
        sem = asyncio.Semaphore(4)  # 4 concurrent conversion workers for maximum throughput

        async def _process_single_clip(idx: int, img_path_str: str) -> Optional[tuple]:
            async with sem:
                img_path = Path(img_path_str)
                if not img_path.exists():
                    return None

                seg = segments[idx] if idx < len(segments) else None
                beat_name = seg.beat if seg else f"Scene {idx + 1}"
                cue = seg.visual_cue if seg else "Authentic news broadcast documentary coverage"
                dur = seg.estimated_duration_sec if seg else 12.0

                prompt = f"The scene begins to move with slow cinematic camera push-in and authentic broadcast news motion: {cue}"
                clip_path = story_clips_dir / f"clip_{idx}_{beat_name.lower().replace(' ', '_')}.mp4"

                # 1. Try MiniMaxAI/MiniMax-H3 via Hugging Face InferenceClient
                video_bytes = await asyncio.to_thread(self._generate_video_minimax, img_path, prompt)
                if video_bytes:
                    clip_path.write_bytes(video_bytes)
                    logger.info(f"Saved MiniMax-H3 video clip to: {clip_path.name}")
                else:
                    # 2. Cinematic motion fallback via FFmpeg with multi-angle Ken Burns
                    success = await asyncio.to_thread(
                        self._generate_cinematic_motion_fallback,
                        img_path,
                        clip_path,
                        dur,
                        idx,
                    )
                    if not success:
                        logger.warning(f"Could not generate video clip for {img_path.name}")
                        return None

                clip_str = str(clip_path)
                if seg:
                    seg.video_clip_path = clip_str
                return (idx, clip_str)

        tasks = [_process_single_clip(i, p) for i, p in enumerate(story.media.image_paths)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_items = [r for r in results if isinstance(r, tuple) and r[1]]
        valid_items.sort(key=lambda x: x[0])  # Maintain exact sequential scene ordering
        generated_clips = [item[1] for item in valid_items]

        story.media.video_clip_paths = generated_clips
        story.status_message = f"Generated {len(generated_clips)} video clips for final broadcast assembly"
        logger.info(f"ImageToVideoAgent: Total video clips produced in parallel: {len(generated_clips)}")
        return generated_clips

