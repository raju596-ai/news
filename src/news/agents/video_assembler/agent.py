import asyncio
import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
from ..base import NewsStory, AgentPhase
from ...config import settings, ROOT_DIR
from ...tools.hardware_encoder import get_best_video_encoder, get_or_create_normalized_clip
from ..image_agent.thumbnail_generator import YouTubeThumbnailGenerator
from .timeline import TimelineSynchronizer

logger = logging.getLogger(__name__)


class VideoAssemblyAgent:
    """Agent 5 — Video Assembly Agent
    - Receives news images / animated video clips, voice audio, and script timing information.
    - Matches visual clips to the narration timeline (10-15s per scene).
    - Layers speech narration, ducked background music, and transition SFX into a master soundtrack.
    - Generates a dedicated high-CTR 1280x720 thumbnail for mobile YouTube feeds.
    - Encodes the body news video to YouTube Standard (1080p, 16:9, 30 FPS, AAC 48kHz) with GPU acceleration.
    - Automatically prepends the Intro video clip (start.mp4) and appends the Ending clip (end.mp4).
    - Uses ultra-fast stream-copy concatenation (-c copy in < 1s) with automatic filter_complex fallback.
    - Generates the final broadcast MP4 video using local FFmpeg.
    """

    def __init__(self):
        self.ffmpeg_path = settings.FFMPEG_PATH
        self.timeline_sync = TimelineSynchronizer()
        self.thumbnail_gen = YouTubeThumbnailGenerator()

    def _prepare_broadcast_soundtrack(self, story: NewsStory, story_dir: Path) -> Path:
        """Create a master audio track layering speech narration, ducked background music, and transition SFX."""
        narration_path = Path(story.media.audio_path).resolve()
        master_audio_path = story_dir / "master_broadcast_audio.wav"

        bg_music = ROOT_DIR / "data" / "background_music.mp3"
        sfx_path = ROOT_DIR / "data" / "sfx_transition.wav"

        # If neither music nor SFX exists, return raw narration
        if not bg_music.exists() and not sfx_path.exists():
            return narration_path

        # Determine transition timestamps from script segments or slide durations
        transition_ms = []
        if story.script and story.script.segments and len(story.script.segments) > 1:
            cum_time = 0.0
            for seg in story.script.segments[:-1]:
                cum_time += (seg.estimated_duration_sec or 12.0)
                transition_ms.append(int(cum_time * 1000))
        elif story.media.image_paths and len(story.media.image_paths) > 1:
            avg_dur = (story.media.audio_duration_sec or 60.0) / len(story.media.image_paths)
            cum_time = 0.0
            for _ in range(len(story.media.image_paths) - 1):
                cum_time += avg_dur
                transition_ms.append(int(cum_time * 1000))

        inputs = ["-i", str(narration_path)]
        filter_parts = []
        mix_inputs = ["[0:a]"]

        # 1. Background Music input
        has_bg = bg_music.exists()
        if has_bg:
            inputs.extend(["-stream_loop", "-1", "-i", str(bg_music.resolve())])
            filter_parts.append("[1:a]volume=0.10[bg];")
            mix_inputs.append("[bg]")

        # 2. Transition SFX input
        has_sfx = sfx_path.exists() and len(transition_ms) > 0
        if has_sfx:
            sfx_input_idx = 2 if has_bg else 1
            inputs.extend(["-i", str(sfx_path.resolve())])
            for s_idx, ms in enumerate(transition_ms[:12]):
                tag = f"sfx{s_idx}"
                filter_parts.append(f"[{sfx_input_idx}:a]volume=0.20,adelay={ms}|{ms}[{tag}];")
                mix_inputs.append(f"[{tag}]")

        filter_parts.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=2[master_a]")
        filter_complex = "".join(filter_parts)

        cmd = [
            self.ffmpeg_path,
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[master_a]",
            "-c:a", "pcm_s16le",
            str(master_audio_path),
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and master_audio_path.exists() and master_audio_path.stat().st_size > 10000:
                logger.info(f"VideoAssemblyAgent: Master broadcast audio track mixed successfully ({master_audio_path.stat().st_size} bytes)")
                return master_audio_path
            logger.warning(f"VideoAssemblyAgent: Master audio mix note: {res.stderr[-200:]}")
        except Exception as e:
            logger.warning(f"VideoAssemblyAgent: Master audio mix fallback: {e}")

        return narration_path

    def _concatenate_clips(self, input_clips: List[Path], output_path: Path):
        """Concatenate intro, body news, and ending clips using instant stream copy with filter_complex fallback."""
        if len(input_clips) == 1:
            shutil.copyfile(input_clips[0], output_path)
            return

        temp_output_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")

        # Optimization 1: Try instant stream-copy concat (< 1 second)
        try:
            concat_list = output_path.with_name(f"{output_path.stem}_stream_list.txt")
            lines = []
            for clip in input_clips:
                escaped_path = clip.resolve().as_posix().replace("'", "'\\''")
                lines.append(f"file '{escaped_path}'")
            concat_list.write_text("\n".join(lines), encoding="utf-8")

            cmd_stream = [
                self.ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                "-movflags", "+faststart",
                str(temp_output_path),
            ]
            res_stream = subprocess.run(cmd_stream, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_stream.returncode == 0 and temp_output_path.exists() and temp_output_path.stat().st_size > 10000:
                logger.info(f"Stream-copy stitching succeeded ({len(input_clips)} clips merged in < 1s)!")
                if output_path.exists():
                    output_path.unlink()
                temp_output_path.replace(output_path)
                return
        except Exception as stream_err:
            logger.debug(f"Direct stream copy note: {stream_err}. Using filter_complex...")

        # Fallback: Robust filter_complex re-encoding
        cmd = [self.ffmpeg_path, "-y"]
        filter_parts = []
        stream_tags = ""

        for i, clip in enumerate(input_clips):
            cmd.extend(["-i", str(clip.resolve())])
            filter_parts.append(
                f"[{i}:v]scale={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={settings.VIDEO_FPS},format=yuv420p[v{i}];"
                f"[{i}:a]aformat=sample_rates={settings.AUDIO_SAMPLE_RATE}:channel_layouts=stereo[a{i}];"
            )
            stream_tags += f"[v{i}][a{i}]"

        filter_complex = "".join(filter_parts) + f"{stream_tags}concat=n={len(input_clips)}:v=1:a=1[v][a]"

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-ar", str(settings.AUDIO_SAMPLE_RATE),
            "-b:a", settings.AUDIO_BITRATE,
            "-movflags", "+faststart",
            str(temp_output_path)
        ])

        logger.info(f"Executing FFmpeg filter_complex stitching ({len(input_clips)} clips)...")
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            if temp_output_path.exists():
                try:
                    temp_output_path.unlink()
                except Exception:
                    pass
            logger.error(f"FFmpeg stitching error: {process.stderr}")
            raise RuntimeError(f"FFmpeg clip stitching failed: {process.stderr[-300:]}")

        if temp_output_path.exists():
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            temp_output_path.replace(output_path)


    async def render_video(self, story: NewsStory) -> str:
        logger.info(f"VideoAssemblyAgent: Assembling YouTube standard news video for '{story.title}'...")
        if not story.media.audio_path or not Path(story.media.audio_path).exists():
            raise ValueError(f"Story {story.id} has no valid audio track for video assembly.")
        if not story.media.image_paths and not story.media.video_clip_paths:
            raise ValueError(f"Story {story.id} has no visuals or video clips for video assembly.")

        story_dir = settings.MEDIA_DIR / story.id
        story_dir.mkdir(parents=True, exist_ok=True)
        body_video_path = story_dir / "body_news_video.mp4"
        final_video_path = story_dir / "final_news_video.mp4"
        concat_list_path = story_dir / "slides_concat.txt"

        # Generate dedicated high-CTR A/B thumbnails (1280x720)
        lead_img = Path(story.media.image_paths[0]) if story.media.image_paths else None
        try:
            self.thumbnail_gen.render_ab_thumbnails(story, lead_image_path=lead_img, save_dir=story_dir)
        except Exception as th_err:
            logger.warning(f"VideoAssemblyAgent: A/B Thumbnail generation note: {th_err}")

        # Mix master soundtrack with background music & transition SFX
        soundtrack_path = self._prepare_broadcast_soundtrack(story, story_dir)

        # 1. Prefer video clips produced by ImageToVideoAgent
        cmd_body = None
        if story.media.video_clip_paths:
            valid_clips = [Path(cp) for cp in story.media.video_clip_paths if Path(cp).exists()]
            if valid_clips:
                logger.info(f"VideoAssemblyAgent: Using {len(valid_clips)} animated video clips for body video...")
                concat_clips_path = story_dir / "clips_concat.txt"
                clip_lines = []
                for p in valid_clips:
                    safe_p = p.resolve().as_posix().replace("'", "'\\''")
                    clip_lines.append(f"file '{safe_p}'")
                concat_clips_path.write_text("\n".join(clip_lines), encoding="utf-8")

                enc_name, enc_args, pix_filter = get_best_video_encoder()
                logger.info(f"VideoAssemblyAgent: Encoding body video via '{enc_name}' hardware encoder...")

                cmd_body = [
                    self.ffmpeg_path,
                    "-y",
                    "-stream_loop", "-1",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_clips_path),
                    "-i", str(soundtrack_path.resolve()),
                    "-vf", f"scale={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,{pix_filter}",
                    "-r", str(settings.VIDEO_FPS),  # 30 FPS
                    *enc_args,
                    "-c:a", "aac",
                    "-ac", "2",  # Stereo
                    "-ar", str(settings.AUDIO_SAMPLE_RATE),  # 48 kHz
                    "-b:a", settings.AUDIO_BITRATE,
                    "-shortest",
                    "-movflags", "+faststart",
                    str(body_video_path),
                ]

        # 2. Fallback to image slides concatenation if no video clips
        if cmd_body is None:
            logger.info("VideoAssemblyAgent: Falling back to image slides concatenation...")
            timelines = self.timeline_sync.calculate_slide_durations(
                image_paths=story.media.image_paths,
                script=story.script,
                total_audio_duration_sec=story.media.audio_duration_sec or 30.0,
            )
            lines = []
            for img_path, dur in timelines:
                safe_p = Path(img_path).resolve().as_posix().replace("'", "'\\''")
                lines.append(f"file '{safe_p}'")
                lines.append(f"duration {dur}")

            if timelines:
                last_p = Path(timelines[-1][0]).resolve().as_posix().replace("'", "'\\''")
                lines.append(f"file '{last_p}'")

            concat_list_path.write_text("\n".join(lines), encoding="utf-8")

            enc_name, enc_args, pix_filter = get_best_video_encoder()
            cmd_body = [
                self.ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_path),
                "-i", str(soundtrack_path.resolve()),
                "-vf", f"scale={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,{pix_filter}",
                "-r", str(settings.VIDEO_FPS),  # 30 FPS
                *enc_args,
                "-c:a", "aac",
                "-ac", "2",  # Stereo
                "-ar", str(settings.AUDIO_SAMPLE_RATE),  # 48 kHz
                "-b:a", settings.AUDIO_BITRATE,
                "-shortest",
                "-movflags", "+faststart",
                str(body_video_path),
            ]

        def _run_body():
            logger.info(f"Rendering body video: {' '.join(cmd_body[:6])} ...")
            process = subprocess.run(cmd_body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process.returncode != 0:
                logger.warning(f"Primary encoder failed ({process.stderr[-200:]}). Retrying with safe libx264...")
                # Safe CPU fallback if GPU encoder failed on filter
                cmd_fallback = [
                    self.ffmpeg_path, "-y",
                    "-stream_loop" if "-stream_loop" in cmd_body else "",
                    "-1" if "-stream_loop" in cmd_body else "",
                    "-f", "concat", "-safe", "0",
                    "-i", cmd_body[cmd_body.index("-i") + 1],
                    "-i", str(soundtrack_path.resolve()),
                    "-vf", f"scale={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={settings.VIDEO_WIDTH}:{settings.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                    "-r", str(settings.VIDEO_FPS),
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", str(settings.AUDIO_SAMPLE_RATE), "-b:a", settings.AUDIO_BITRATE,
                    "-shortest", "-movflags", "+faststart",
                    str(body_video_path)
                ]
                cmd_fallback = [x for x in cmd_fallback if x]
                proc2 = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if proc2.returncode != 0:
                    raise RuntimeError(f"FFmpeg render error: {proc2.stderr[-300:]}")
            return str(body_video_path)

        await asyncio.to_thread(_run_body)

        # 4. Check for Intro (prefix) and Ending (suffix) video clips
        clips_to_stitch: List[Path] = []

        intro_clip = settings.get_intro_video_path()
        if intro_clip:
            norm_intro = get_or_create_normalized_clip(intro_clip)
            logger.info(f"Adding normalized Intro prefix: {norm_intro.name}")
            clips_to_stitch.append(norm_intro)
        else:
            logger.warning(f"Intro prefix clip (start.mp4) not found at {settings.INTRO_VIDEO_PATH}")

        clips_to_stitch.append(body_video_path)

        end_clip = settings.get_end_video_path()
        if end_clip:
            norm_end = get_or_create_normalized_clip(end_clip)
            logger.info(f"Adding normalized Ending suffix: {norm_end.name}")
            clips_to_stitch.append(norm_end)
        else:
            logger.warning(f"Ending suffix clip (end.mp4) not found at {settings.END_VIDEO_PATH}")


        # 5. Stitch Intro + Body + Ending into final_news_video.mp4
        if len(clips_to_stitch) > 1:
            logger.info(f"Stitching {len(clips_to_stitch)} clips into final news video: {final_video_path}")
            await asyncio.to_thread(self._concatenate_clips, clips_to_stitch, final_video_path)
        else:
            shutil.copyfile(body_video_path, final_video_path)

        story.media.video_path = str(final_video_path)
        story.status = AgentPhase.VIDEO_ASSEMBLY
        story.status_message = "Broadcast video ready with Intro & Ending clips (1080p, 30 FPS, AAC 48kHz)"

        # 6. Generate and save YouTube upload metadata file (metadata.txt) & matching named video
        try:
            from ...tools.youtube_metadata import save_metadata_file, get_story_download_basename
            base_name = get_story_download_basename(story, story.id)
            named_video = story_dir / f"{base_name}.mp4"
            if final_video_path.exists():
                try:
                    shutil.copyfile(final_video_path, named_video)
                except Exception:
                    pass

            meta_path = save_metadata_file(story, story_dir)
            story.media.metadata_path = str(meta_path)
            logger.info(f"VideoAssemblyAgent: Saved matching files '{named_video.name}' and '{base_name}.txt'")
        except Exception as meta_err:
            logger.warning(f"VideoAssemblyAgent: Note on file save: {meta_err}")

        # 7. Render 9:16 vertical video (Shorts / Reels) if requested
        if getattr(story, "aspect_ratio", "16:9") in ("9:16", "both"):
            try:
                await self.render_vertical_video(story)
            except Exception as v_err:
                logger.warning(f"VideoAssemblyAgent: Vertical video render note: {v_err}")

        # 8. Storage Maintenance: Prune scratch working files (preserves final video, thumbnail, & metadata)
        try:
            from ...tools.maintenance import cleanup_story_intermediates
            cleanup_story_intermediates(story.id)
        except Exception as maint_err:
            logger.debug(f"Maintenance note for story {story.id}: {maint_err}")

        return str(final_video_path)

    async def render_vertical_video(self, story: NewsStory) -> str:
        """Render dedicated 9:16 vertical video (1080x1920) for YouTube Shorts and Instagram Reels."""
        logger.info(f"VideoAssemblyAgent: Rendering 9:16 vertical video for '{story.title}'...")
        story_dir = settings.MEDIA_DIR / story.id
        story_dir.mkdir(parents=True, exist_ok=True)
        vertical_video_path = story_dir / "final_news_video_vertical.mp4"

        soundtrack_path = self._prepare_broadcast_soundtrack(story, story_dir)
        timelines = self.timeline_sync.calculate_slide_durations(
            image_paths=story.media.image_paths,
            script=story.script,
            total_audio_duration_sec=story.media.audio_duration_sec or 30.0,
        )

        concat_list_path = story_dir / "vertical_slides_concat.txt"
        lines = []
        for img_path, dur in timelines:
            safe_p = Path(img_path).resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{safe_p}'")
            lines.append(f"duration {dur}")

        if timelines:
            last_p = Path(timelines[-1][0]).resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{last_p}'")

        concat_list_path.write_text("\n".join(lines), encoding="utf-8")

        # 1080x1920 with blurred background fill + sharp centered slide
        vw = settings.VERTICAL_VIDEO_WIDTH
        vh = settings.VERTICAL_VIDEO_HEIGHT

        filter_str = (
            f"split[fg_raw][bg_raw];"
            f"[bg_raw]scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},boxblur=25:5[bg];"
            f"[fg_raw]scale={vw}:-1:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
        )

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-i", str(soundtrack_path.resolve()),
            "-filter_complex", filter_str,
            "-r", str(settings.VIDEO_FPS),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ac", "2",
            "-ar", str(settings.AUDIO_SAMPLE_RATE),
            "-b:a", settings.AUDIO_BITRATE,
            "-shortest",
            "-movflags", "+faststart",
            str(vertical_video_path),
        ]

        def _run_vertical():
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0 or not vertical_video_path.exists():
                logger.error(f"FFmpeg vertical render error: {res.stderr[-200:]}")
                raise RuntimeError(f"Vertical video render failed: {res.stderr[-200:]}")
            return str(vertical_video_path)

        await asyncio.to_thread(_run_vertical)
        story.media.vertical_video_path = str(vertical_video_path)
        logger.info(f"VideoAssemblyAgent: 9:16 vertical video rendered successfully at {vertical_video_path}")
        return str(vertical_video_path)
