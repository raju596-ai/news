import json
import logging
from typing import List
from ..base import NewsStory, StoryScript, ScriptSegment, AgentPhase
from ..llm_factory import MultiProviderLLM
from .prompts import SCRIPT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class NewsScriptAgent:
    """Agent B — 5-Minute News Script Agent
    Generates a full broadcast script for YouTube Standard Video (1080p, 16:9, 30 FPS):
    1. 🎯 Hook: 20–25 sec (45–55 words)
    2. 📰 What Happened: 50–60 sec (105–125 words)
    3. 🔎 Key Details: 100–120 sec (220–250 words)
    4. 🌍 Why It Matters: 50–60 sec (105–125 words)
    5. 📌 Latest Update: 45–55 sec (95–115 words)
    6. 🎬 Closing: 15–20 sec (30–40 words)
    Total: ~5 min (~280–290s of speech + 16s intro/outro = ~300s total video) | ~600–680 words.
    Divides the script into 22-26 distinct scenes (10-15s each) for continuous visual transitions.
    """

    def __init__(self):
        self.llm = MultiProviderLLM()

    def _split_into_12s_scenes(self, section_name: str, text: str, visual_cue_hint: str) -> List[ScriptSegment]:
        """Subdivide a narrative section into 10-15 second spoken scenes (~25-30 words each)."""
        words = text.split()
        if not words:
            return []

        # Target ~26 words per scene (~11-13 seconds of broadcast speech)
        chunk_size = 26
        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
        segments = []

        for idx, chunk in enumerate(chunks, 1):
            sub_text = " ".join(chunk)
            dur = round(max(10.0, min(15.0, len(chunk) / 2.2)), 1)
            beat_label = f"{section_name} Pt.{idx}" if len(chunks) > 1 else section_name
            cue = f"{visual_cue_hint} (Angle {idx})" if len(chunks) > 1 else visual_cue_hint
            segments.append(
                ScriptSegment(
                    beat=beat_label,
                    narration=sub_text,
                    visual_cue=cue,
                    estimated_duration_sec=dur,
                )
            )

        return segments

    async def generate_script(self, story: NewsStory) -> StoryScript:
        logger.info(f"NewsScriptAgent: Writing 5-minute broadcast script for '{story.title}' (~600-680 words)...")
        prompt = (
            f"STORY TITLE: {story.title}\n"
            f"SOURCE: {story.source}\n"
            f"REGION: {story.region.value}\n"
            f"CATEGORY: {story.category}\n"
            f"SUMMARY / CONTEXT:\n{story.summary}\n\n"
            f"ORIGINAL URL: {story.url}\n\n"
            "Generate the authoritative 5-minute YouTube Standard news video broadcast script following the required "
            "6-section format (~600-680 words) and 22-26 scene segments in valid JSON."
        )

        try:
            raw_response, model_used, _ = await self.llm.generate(SCRIPT_SYSTEM_PROMPT, prompt)
            clean_text = raw_response.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            parsed = json.loads(clean_text.strip())

            hook = parsed.get("hook", "").strip()
            what_happened = parsed.get("what_happened", "").strip()
            key_details = parsed.get("key_details", "").strip()
            why_it_matters = parsed.get("why_it_matters", "").strip()
            latest_update = parsed.get("latest_update", parsed.get("current_status", "")).strip()
            closing = parsed.get("closing", "").strip()

            raw_segments = parsed.get("segments", [])
            segments: List[ScriptSegment] = []

            # If model returned fine-grained segments of 10-15s, use them
            if raw_segments and len(raw_segments) >= 8:
                for s in raw_segments:
                    narration = s.get("narration", "").strip()
                    w_count = len(narration.split())
                    dur = max(10.0, min(15.0, round(w_count / 2.2, 1)))
                    segments.append(
                        ScriptSegment(
                            beat=s.get("section", s.get("beat", "Detail")),
                            narration=narration,
                            visual_cue=s.get("visual_cue", "High-definition 1080p news visual"),
                            estimated_duration_sec=dur,
                        )
                    )
            else:
                # Subdivide sections into 10-15s scenes to guarantee visual transitions
                segments.extend(self._split_into_12s_scenes("Hook", hook, "Breaking news alert"))
                segments.extend(self._split_into_12s_scenes("What Happened", what_happened, "Event footage & press conference"))
                segments.extend(self._split_into_12s_scenes("Key Details", key_details, "Data charts, technical specs & location maps"))
                segments.extend(self._split_into_12s_scenes("Why It Matters", why_it_matters, "Geopolitical impact & industry analysis"))
                segments.extend(self._split_into_12s_scenes("Latest Update", latest_update, "Live updates & official statements"))
                segments.extend(self._split_into_12s_scenes("Closing", closing, "NewsIntel broadcast desk & subscribe call-to-action"))

            total_words = sum(len(s.narration.split()) for s in segments)
            total_sec = sum(s.estimated_duration_sec for s in segments)

            story_script = StoryScript(
                story_id=story.id,
                headline=parsed.get("headline", story.title),
                hook=hook,
                what_happened=what_happened,
                key_details=key_details,
                why_it_matters=why_it_matters,
                latest_update=latest_update,
                current_status=latest_update,
                closing=closing,
                segments=segments,
                total_words=total_words,
                estimated_seconds=total_sec,
            )
            story.script = story_script
            story.status = AgentPhase.SCRIPT_GENERATION
            story.status_message = f"5-Min Script generated ({total_words} words, ~{int(total_sec)}s, {len(segments)} scenes) via {model_used}"
            return story_script

        except Exception as e:
            logger.error(f"NewsScriptAgent: LLM script generation failed ({e}). Building full 5-min fallback template.")
            return self._build_fallback_3min_script(story)

    def _build_fallback_3min_script(self, story: NewsStory) -> StoryScript:
        """Construct an emergency 5-minute, 24-scene broadcast script (~640 words) adhering strictly to the user format."""
        hook_text = (
            f"Breaking news alert in {story.category}: critical global developments are actively unfolding right now regarding {story.title}, "
            "as leading international observers, sector specialists, intelligence analysts, and senior regulatory bodies urgently convene to address verified official reports breaking across world capitals. "
            "Markets and diplomatic channels are reacting with unprecedented speed as the full scope of this breaking story comes into sharp focus."
        )
        what_happened_text = (
            f"According to verified investigative reports published in the last twenty-four hours by {story.source}, {story.summary}. "
            "Government ministries, international watchdogs, and major industry stakeholders have officially confirmed that high-level consultations are underway to manage immediate fallout and establish coordinated regional protocols. "
            "Independent analysts and veteran policy advisors emphasize that this incident marks a critical turning point in institutional oversight, demanding unprecedented operational coordination across international borders and public sectors. "
            "Early eyewitness and official documentation indicates that key operations were impacted within hours of the initial announcement, triggering automated continuity protocols across affected jurisdictions."
        )
        key_details_text = (
            "Delving deeply into the core technical, geopolitical, and strategic details of this major development, officials have released comprehensive documentation highlighting vital milestones, forensics, and timeline data. "
            "The initial phase directly impacted primary institutional stakeholders and local networks, while subsequent technical evaluations revealed substantial ramifications across regional communication channels, enterprise logistics, critical infrastructure, and regulatory pipelines. "
            "Engineering audits and independent scientific panels emphasize that the scale of this breakthrough exceeds all prior projections, requiring immediate regulatory adjustments, enhanced security protocols, and international compliance frameworks. "
            "Official statements submitted to international governing councils confirm that secondary multi-stakeholder reviews will conclude within the coming days, establishing a permanent operational baseline. "
            "Financial analysts and market observers also note that capital allocation toward related infrastructure and security safeguards has accelerated substantially, with initial fiscal impacts already materializing across primary global exchange markets, sovereign funds, and institutional portfolios worldwide. "
            "Furthermore, internal oversight committees have scheduled daily evidentiary hearings to evaluate long-term systemic resilience and prevent future procedural bottlenecks."
        )
        why_it_matters_text = (
            "The strategic implications of this story cannot be understated for policymakers, industry leaders, global investors, and citizens alike. "
            "Market strategists and institutional watchdogs note that this development sets a transformative precedent for global governance, directly influencing commercial direction, technological standards, supply chain sovereignty, and cross-border partnerships. "
            "For organizations and communities navigating these emerging shifts, the outcome represents a fundamental evolution in competitive resilience, consumer transparency, and long-term risk management in an increasingly interconnected global economy."
        )
        latest_update_text = (
            "In the latest update unfolding this hour, authorities have issued a formal status briefing outlining immediate next steps, interim safeguards, and containment measures. "
            "Diplomatic delegations, civil society representatives, and corporate executives are scheduled to convene emergency bilateral sessions tomorrow morning to finalize collaborative measures, while specialized monitoring task forces continue to provide real-time updates as key developments progress around the clock. "
            "Official spokespersons have committed to publishing updated findings at noon to maintain full public transparency."
        )
        closing_text = (
            "Stay tuned to NewsIntel for continuous live coverage, expert analysis, and in-depth investigative breakdowns as this story develops. "
            "Be sure to like, subscribe, and hit the notification bell to stay ahead of the world."
        )

        segments = []
        segments.extend(self._split_into_12s_scenes("Hook", hook_text, "Breaking news control room alert"))
        segments.extend(self._split_into_12s_scenes("What Happened", what_happened_text, "Event footage & official press conference"))
        segments.extend(self._split_into_12s_scenes("Key Details", key_details_text, "Data charts, technical specs & location maps"))
        segments.extend(self._split_into_12s_scenes("Why It Matters", why_it_matters_text, "Geopolitical impact & industry market analysis"))
        segments.extend(self._split_into_12s_scenes("Latest Update", latest_update_text, "Live updates & emergency briefing"))
        segments.extend(self._split_into_12s_scenes("Closing", closing_text, "NewsIntel broadcast desk & subscribe call-to-action"))

        total_words = sum(len(s.narration.split()) for s in segments)
        total_sec = sum(s.estimated_duration_sec for s in segments)

        fallback_script = StoryScript(
            story_id=story.id,
            headline=story.title,
            hook=hook_text,
            what_happened=what_happened_text,
            key_details=key_details_text,
            why_it_matters=why_it_matters_text,
            latest_update=latest_update_text,
            current_status=latest_update_text,
            closing=closing_text,
            segments=segments,
            total_words=total_words,
            estimated_seconds=total_sec,
        )
        story.script = fallback_script
        story.status = AgentPhase.SCRIPT_GENERATION
        story.status_message = f"5-Min Script created via broadcast template ({total_words} words, ~{int(total_sec)}s, {len(segments)} scenes)"
        return fallback_script
