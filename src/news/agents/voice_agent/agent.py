import logging
from pathlib import Path
from typing import Tuple
from ..base import NewsStory, AgentPhase
from ...config import settings
from .tts_engine import TTSEngine
from ..llm_factory import MultiProviderLLM

logger = logging.getLogger(__name__)


class VoiceGenerationAgent:
    """Agent 4 — Voice Generation Agent
    - Receives finalized 2-minute script.
    - Converts narrative beats into natural broadcast audio.
    - Supports regional language translation (Telugu, Hindi) with native neural voices.
    - Generates high-fidelity MP3 audio track.
    - Inspects and records exact audio duration for video synchronization.
    """

    def __init__(self):
        self.tts = TTSEngine()
        self.llm = MultiProviderLLM(primary_model=settings.SCRIPT_MODEL)

    async def _translate_text(self, text: str, target_lang: str) -> str:
        """Translate news narration into authentic vernacular Telugu or Hindi idiom."""
        lang_map = {"te": "Telugu (తెలుగు)", "hi": "Hindi (हिन्दी)"}
        target_name = lang_map.get(target_lang.lower(), target_lang)
        prompt = (
            f"You are a professional broadcast news translator for Indian regional television.\n"
            f"Translate the following news script narration into authentic, spoken-journalistic {target_name}.\n"
            f"Maintain urgent, formal, journalistic tone suitable for television news anchors.\n"
            f"Output ONLY the translated script text, no english commentary or notes.\n\n"
            f"Text to translate:\n{text}"
        )
        try:
            res, _, _ = await self.llm.generate("You are an expert news translator.", prompt)
            clean = res.strip().replace("```", "")
            return clean if len(clean) > 5 else text
        except Exception as e:
            logger.warning(f"Translation to {target_lang} fallback note: {e}")
            return text

    async def generate_voice(self, story: NewsStory) -> Tuple[str, float]:
        lang = getattr(story, "language", "en") or "en"
        logger.info(f"VoiceGenerationAgent: Generating voiceover for '{story.title}' (lang={lang})...")
        if not story.script:
            raise ValueError(f"Story {story.id} does not have a finalized script to voice.")

        audio_output_path = settings.MEDIA_DIR / story.id / "narration.mp3"

        # Assemble speech narration text with dual-anchor role tagging
        if story.script.segments:
            seg_items = []
            for s in story.script.segments:
                beat_lower = s.beat.lower()
                if any(k in beat_lower for k in ["hook", "why it matters", "closing", "impact"]):
                    role = "anchor"
                else:
                    role = "reporter"

                narration_text = s.narration
                if lang.lower() in ["te", "telugu", "hi", "hindi"]:
                    narration_text = await self._translate_text(narration_text, lang)

                seg_items.append((narration_text, role))

            audio_path, duration_sec = await self.tts.synthesize_segments(
                segments=seg_items,
                output_path=audio_output_path,
                region=story.region,
                language=lang,
            )
        else:
            full_narration = f"{story.script.hook} ... {story.script.what_happened} ... {story.script.key_details} ... {story.script.why_it_matters} ... {story.script.latest_update or story.script.current_status} ... {story.script.closing}"
            if lang.lower() in ["te", "telugu", "hi", "hindi"]:
                full_narration = await self._translate_text(full_narration, lang)

            audio_path, duration_sec = await self.tts.synthesize_speech(
                full_text=full_narration,
                output_path=audio_output_path,
                region=story.region,
                language=lang,
            )

        story.media.audio_path = audio_path
        story.media.audio_duration_sec = duration_sec
        story.status = AgentPhase.VOICE_GENERATION
        story.status_message = f"Audio synthesized ({duration_sec:.1f}s) in {lang.upper()} with neural voices"

        return audio_path, duration_sec
