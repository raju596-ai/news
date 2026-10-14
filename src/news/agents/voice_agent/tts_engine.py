import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import edge_tts
from ...config import settings
from ..base import Region

logger = logging.getLogger(__name__)


class TTSEngine:
    """Enterprise Text-to-Speech Engine with neural voices and duration inspection."""

    def __init__(self):
        self.ffmpeg_path = settings.FFMPEG_PATH

    def get_voice_for_region(self, region: Region, role: str = "anchor", language: str = "en") -> str:
        """Select appropriate neural broadcast voice based on news region, anchor role, and vernacular language."""
        lang_lower = (language or "en").lower().strip()
        if lang_lower in ["te", "telugu"]:
            return settings.VOICE_TELUGU_REPORTER if role == "reporter" else settings.VOICE_TELUGU_ANCHOR
        elif lang_lower in ["hi", "hindi"]:
            return settings.VOICE_HINDI_REPORTER if role == "reporter" else settings.VOICE_HINDI_ANCHOR
        elif region == Region.INDIA:
            return settings.VOICE_INDIA_REPORTER if role == "reporter" else settings.VOICE_INDIA_ANCHOR
        return settings.VOICE_WORLD_REPORTER if role == "reporter" else settings.VOICE_WORLD_ANCHOR

    async def get_audio_duration(self, audio_file: Path) -> float:
        """Inspect accurate audio duration in seconds using ffprobe or ffmpeg."""
        ffprobe_path = self.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg.EXE", "ffprobe.exe")
        if not Path(ffprobe_path).exists():
            ffprobe_path = "ffprobe"

        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_file),
        ]

        def _run_probe():
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                return float(res.stdout.strip())
            except Exception as e:
                logger.debug(f"ffprobe failed ({e}), falling back to file-size estimate")
                # Fallback: estimate from MP3 byte size (~16KB per second at 128kbps)
                size = audio_file.stat().st_size
                return max(5.0, round(size / 16000.0, 1))

        return await asyncio.to_thread(_run_probe)

    async def synthesize_speech(
        self,
        full_text: str,
        output_path: Path,
        region: Region,
        role: str = "anchor",
        language: str = "en",
    ) -> Tuple[str, float]:
        """Synthesize natural narration audio file and return (path, duration_seconds)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        voice = self.get_voice_for_region(region, role=role, language=language)

        logger.info(f"TTSEngine: Synthesizing speech with voice '{voice}' ({role}, lang={language})...")
        communicate = edge_tts.Communicate(text=full_text, voice=voice, rate="+2%")
        await communicate.save(str(output_path))

        duration_sec = await self.get_audio_duration(output_path)
        logger.info(f"TTSEngine: Audio generated ({duration_sec:.1f}s) at {output_path}")
        return str(output_path), duration_sec

    async def synthesize_segments(
        self,
        segments: list,
        output_path: Path,
        region: Region,
        language: str = "en",
    ) -> Tuple[str, float]:
        """Synthesize multiple script segments using dual-anchor voices and concatenate seamlessly."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not segments:
            raise ValueError("No text segments provided for speech synthesis.")

        if len(segments) == 1:
            return await self.synthesize_speech(segments[0][0], output_path, region, role=segments[0][1], language=language)

        temp_dir = output_path.parent / "temp_audio_segments"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_files = []

        try:
            for idx, (text, role) in enumerate(segments):
                voice = self.get_voice_for_region(region, role=role, language=language)
                seg_path = temp_dir / f"seg_{idx}_{role}.mp3"
                clean_text = text.strip()
                if not clean_text:
                    continue
                communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate="+2%")
                await communicate.save(str(seg_path))
                if seg_path.exists() and seg_path.stat().st_size > 500:
                    temp_files.append(seg_path)

            if not temp_files:
                raise RuntimeError("Dual-anchor synthesis produced no valid audio segments.")

            # Concatenate all segment MP3s via FFmpeg concat protocol
            concat_list = temp_dir / "concat_audio.txt"
            lines = [f"file '{p.resolve().as_posix()}'" for p in temp_files]
            concat_list.write_text("\n".join(lines), encoding="utf-8")

            cmd = [
                self.ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list.resolve()),
                "-c", "copy",
                str(output_path),
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0 or not output_path.exists() or output_path.stat().st_size < 1000:
                # Re-encoding fallback
                cmd_reencode = [
                    self.ffmpeg_path,
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_list.resolve()),
                    "-c:a", "libmp3lame",
                    "-b:a", "192k",
                    str(output_path),
                ]
                subprocess.run(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

            duration_sec = await self.get_audio_duration(output_path)
            logger.info(f"TTSEngine: Dual-anchor audio successfully synthesized ({duration_sec:.1f}s) across {len(temp_files)} segments")
            return str(output_path), duration_sec
        finally:
            try:
                for f in temp_files:
                    if f.exists():
                        f.unlink()
                if (temp_dir / "concat_audio.txt").exists():
                    (temp_dir / "concat_audio.txt").unlink()
                temp_dir.rmdir()
            except Exception:
                pass
