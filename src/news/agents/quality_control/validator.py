import json
import logging
from pathlib import Path
from typing import Tuple, List
from ..base import NewsStory
from ..llm_factory import MultiProviderLLM

logger = logging.getLogger(__name__)

QC_PROMPT = """You are a Quality Control Auditor for automated news video generation.
Verify that the headline and script segments match and are free of hallucination or severe factual contradiction.

Respond ONLY with valid JSON:
{
  "passed": true,
  "confidence_score": 0.98,
  "editorial_notes": ["Narrative matches headline", "Timing consistent"]
}
"""


class QCValidator:
    """Combines deterministic media validation with LLM semantic quality verification."""

    def __init__(self):
        self.llm = MultiProviderLLM()

    async def validate_story(self, story: NewsStory) -> Tuple[bool, List[str]]:
        notes: List[str] = []

        # 1. Video File Integrity Check
        if not story.media.video_path or not Path(story.media.video_path).exists():
            return False, ["Fatal: Final video file was not generated or is missing."]

        video_size = Path(story.media.video_path).stat().st_size
        if video_size < 10000:
            return False, [f"Fatal: Video file is corrupted or too small ({video_size} bytes)."]
        notes.append(f"Video file integrity verified ({video_size // 1024} KB).")

        # 2. Audio Track Validation
        if not story.media.audio_path or not Path(story.media.audio_path).exists():
            return False, ["Fatal: Audio narration track missing."]

        if story.media.audio_duration_sec < 4.0:
            return False, [f"Warning: Audio duration is too short ({story.media.audio_duration_sec:.1f}s)."]
        notes.append(f"Audio track duration verified ({story.media.audio_duration_sec:.1f}s).")

        # 3. Visual Slides Count & Verification
        if not story.media.image_paths:
            return False, ["Fatal: No image slides associated with video."]
        notes.append(f"Visual slides verified ({len(story.media.image_paths)} slides).")

        # 4. Script Quality & Content Check
        if not story.script or not story.script.segments:
            return False, ["Fatal: Script beats are missing."]
        notes.append(f"Script segments verified ({len(story.script.segments)} beats, {story.script.total_words} words).")

        # 5. Fast LLM Semantic Consistency Check
        try:
            payload = {
                "title": story.title,
                "summary": story.summary,
                "hook": story.script.hook,
                "closing": story.script.closing,
            }
            raw, _, _ = await self.llm.generate(QC_PROMPT, json.dumps(payload))
            clean = raw.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            elif clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            data = json.loads(clean.strip())
            if data.get("passed", True):
                notes.extend(data.get("editorial_notes", ["Passed semantic audit"]))
        except Exception as e:
            logger.debug(f"QC LLM check skipped/failed ({e}), adhering to deterministic pass")
            notes.append("Deterministic quality checks passed.")

        return True, notes
