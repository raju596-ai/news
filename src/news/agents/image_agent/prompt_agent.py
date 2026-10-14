"""News Image Prompt Agent
Generates realistic, photojournalistic text-to-image prompts tailored for news video broadcast visuals.
Specialized for state-of-the-art models including Qwen-Image-2.1 and FLUX.
"""

import json
import logging
import re
from typing import List, Dict, Optional
from ..base import NewsStory, ScriptSegment
from ..llm_factory import MultiProviderLLM
from ...tools.news_fetcher import sanitize_news_headline

logger = logging.getLogger(__name__)

PROMPT_SYSTEM_INSTRUCTIONS = """You are an expert Photojournalism Art Director for a premier broadcast television news network.
Your job is to generate highly realistic, authentic, editorial photo prompts for an AI image generator (like Qwen-Image-2.1 or FLUX).

Requirements for each image prompt:
1. Editorial Realism: Must look like an authentic documentary press photograph captured on a 35mm or 50mm camera lens by a professional photojournalist (Reuters, Associated Press, AFP style).
2. Topic Specificity: Directly depict the specific people, agencies, hardware, buildings, locations, or economic/geopolitical realities described in the news story.
3. Natural Aesthetics: Natural lighting, realistic skin textures, atmospheric depth, realistic press conference or field setting.
4. Clean Visuals: NO fictional sci-fi glow, NO cartoonish 3D rendering, NO floating text, watermarks, or artificial symbols.
5. Diversity: Each scene beat MUST have a different camera angle, framing, or aspect of the story (e.g., wide establishing shot, medium press briefing, detailed technical hardware or documentation, regional impact view).

Output strictly valid JSON:
{
  "lead_prompt": "Ultra-realistic 35mm editorial news photo of ...",
  "scene_prompts": [
    {
      "beat": "Hook",
      "prompt": "Authentic press photograph, eye-level framing showing ..."
    },
    {
      "beat": "What Happened",
      "prompt": "Documentary wide-angle news photograph capturing ..."
    },
    {
      "beat": "Key Details",
      "prompt": "Close-up photojournalistic capture of official documents, monitors, or technical equipment showing ..."
    },
    {
      "beat": "Why It Matters",
      "prompt": "Medium shot editorial documentary photo illustrating the broader economic, civic, or geopolitical impact ..."
    },
    {
      "beat": "Latest Update",
      "prompt": "Live newsfield photography showing the current immediate developments at the scene ..."
    },
    {
      "beat": "Closing",
      "prompt": "Cinematic broadcast news establishing shot showing the institutional headquarters or landscape ..."
    }
  ]
}
"""


class NewsImagePromptAgent:
    """Generates authentic, scene-specific photojournalism prompts for text-to-image AI models."""

    def __init__(self):
        self.llm = MultiProviderLLM()

    async def generate_prompts_for_story(
        self,
        story: NewsStory,
        segments: Optional[List[ScriptSegment]] = None,
    ) -> Dict[str, any]:
        """Generate high-fidelity, distinct editorial prompts for each scene of the news story."""
        clean_headline = sanitize_news_headline(story.title)
        beats_context = []
        if segments:
            for s in segments[:8]:
                beats_context.append(f"- Beat: {s.beat} | Cue: {s.visual_cue} | Narration: {s.narration[:120]}")

        prompt_input = (
            f"NEWS STORY TITLE: {clean_headline}\n"
            f"SOURCE: {story.source}\n"
            f"CATEGORY: {story.category}\n"
            f"REGION: {story.region.value}\n"
            f"SUMMARY: {story.summary}\n\n"
            f"SCENE BEATS TO VISUALIZE:\n" + ("\n".join(beats_context) if beats_context else "Standard 6-Beat Broadcast News Structure") + "\n\n"
            "Generate the authoritative JSON containing the lead_prompt and scene_prompts for realistic image generation."
        )

        try:
            raw, model_used, _ = await self.llm.generate(PROMPT_SYSTEM_INSTRUCTIONS, prompt_input)
            clean = raw.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            elif clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]

            parsed = json.loads(clean.strip())
            logger.info(f"NewsImagePromptAgent: Generated realistic prompts for '{clean_headline}' via {model_used}")
            return parsed
        except Exception as e:
            logger.warning(f"NewsImagePromptAgent: LLM prompt generation fallback activated ({e})")
            return self._build_deterministic_prompts(story, segments)

    def _build_deterministic_prompts(
        self,
        story: NewsStory,
        segments: Optional[List[ScriptSegment]] = None,
    ) -> Dict[str, any]:
        """Construct realistic deterministic photojournalism prompts based on story metadata."""
        clean_headline = sanitize_news_headline(story.title)
        clean_headline = re.sub(r"\s+-\s+[A-Za-z0-9 ]+$", "", clean_headline)
        clean_headline = re.sub(r"[^\w\s-]", "", clean_headline).strip()

        lead = (
            f"Award-winning documentary news photography, 35mm lens, authentic Reuters editorial style. "
            f"Press coverage of {clean_headline}, natural broadcast lighting, realistic textures, 8k resolution."
        )

        scene_templates = [
            ("Hook", f"Wide-angle press conference and breaking news reporting scene regarding {clean_headline}, journalistic documentary photograph."),
            ("What Happened", f"High-detail photojournalism shot showing the core event and official spokespersons for {clean_headline}, 50mm lens."),
            ("Key Details", f"Medium-shot documentary photograph of technical analysis, verified documentation, or institutional meeting regarding {clean_headline}."),
            ("Why It Matters", f"Editorial news photograph showing the regional and economic impact related to {clean_headline}, natural candid daylight."),
            ("Latest Update", f"Live press dispatch photography showing official government briefing or active scene related to {clean_headline}."),
            ("Closing", f"Authoritative news broadcast establishing shot of the relevant institutional headquarters, national flags, and official chamber regarding {clean_headline}."),
        ]

        scene_prompts = []
        for beat, p in scene_templates:
            scene_prompts.append({"beat": beat, "prompt": p})

        return {
            "lead_prompt": lead,
            "scene_prompts": scene_prompts,
        }

