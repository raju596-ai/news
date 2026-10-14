import asyncio
import logging
from typing import List, Tuple, Optional
from ..base import NewsStory, Region, AgentPhase, PipelineEvent
from ..news_collector import NewsCollectionAgent
from ..script_agent import NewsScriptAgent
from ..image_agent import ImageResearchAgent
from ..video_clip_agent import ImageToVideoAgent
from ..voice_agent import VoiceGenerationAgent
from ..video_assembler import VideoAssemblyAgent
from ..quality_control import QualityControlAgent
from .state import global_state, global_broadcaster

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Master/Orchestrator Agent
    - Starts the entire end-to-end workflow.
    - Creates two parallel pipelines:
      1. Global News Pipeline
      2. India News Pipeline
    - Selects Top 2 World and Top 2 India stories.
    - Coordinates child agents for each story:
      - Script Agent
      - Image Agent (Script-Referenced Prompts & Image Generation)
      - Image-to-Video Agent (MiniMaxAI/MiniMax-H3 Animated Clips)
      - Voice Generation Agent
      - Video Assembly Agent (FFmpeg Stitched 1080p Broadcast Video)
      - Quality Control Agent
    - Tracks status of every story and handles failures/retries.
    """

    def __init__(self):
        self.news_collector = NewsCollectionAgent()
        self.script_agent = NewsScriptAgent()
        self.image_agent = ImageResearchAgent()
        self.image_to_video_agent = ImageToVideoAgent()
        self.voice_agent = VoiceGenerationAgent()
        self.video_assembler = VideoAssemblyAgent()
        self.qc_agent = QualityControlAgent()


    async def emit_event(
        self,
        stage: AgentPhase,
        message: str,
        story: Optional[NewsStory] = None,
        progress: int = 0,
    ):
        event = PipelineEvent(
            stage=stage,
            story_id=story.id if story else None,
            story_title=story.title if story else None,
            region=story.region if story else None,
            message=message,
            progress=progress,
        )
        global_state.event_history.append(event)
        await global_broadcaster.broadcast(event)

    async def run_full_pipeline(self, auto_render_videos: bool = True) -> Tuple[List[NewsStory], List[NewsStory]]:
        """Executes the master news video workflow."""
        if global_state.is_running:
            logger.warning("Pipeline is already executing. Returning current state.")
            return global_state.world_stories, global_state.india_stories

        global_state.is_running = True
        global_state.active_phase = AgentPhase.ORCHESTRATOR
        global_state.overall_progress = 5

        try:
            await self.emit_event(
                AgentPhase.ORCHESTRATOR,
                "Master Orchestrator initiated parallel Global & India News Pipelines",
                progress=5,
            )

            # 1. Parallel News Collection & Ranking (Top 5 World + Top 5 India)
            global_state.active_phase = AgentPhase.NEWS_COLLECTION
            await self.emit_event(
                AgentPhase.NEWS_COLLECTION,
                "Ingesting 24-hour real-time feeds from Google News Global, BBC, Google News India, The Hindu, NDTV...",
                progress=15,
            )

            world_stories, india_stories = await self.news_collector.collect_pipeline()

            for s in world_stories + india_stories:
                global_state.register_story(s)

            await self.emit_event(
                AgentPhase.NEWS_COLLECTION,
                f"Curated and ranked {len(world_stories)} World Stories and {len(india_stories)} India Stories.",
                progress=30,
            )

            # 2. Process stories through Script, Image, Voice, Assembly, and QC
            all_stories = world_stories + india_stories
            total_stories = len(all_stories)

            if auto_render_videos:
                # Process in managed concurrent batches to respect LLM rate limits
                concurrency_semaphore = asyncio.Semaphore(2)

                async def _process_with_sem(story: NewsStory, idx: int):
                    async with concurrency_semaphore:
                        await self.process_story_full(story)
                        # Increment progress
                        done_count = sum(1 for s in all_stories if s.status in (AgentPhase.COMPLETED, AgentPhase.FAILED))
                        global_state.overall_progress = min(95, 30 + int((done_count / total_stories) * 65))

                tasks = [_process_with_sem(story, i) for i, story in enumerate(all_stories)]
                await asyncio.gather(*tasks, return_exceptions=True)

            global_state.is_running = False
            global_state.active_phase = AgentPhase.COMPLETED
            global_state.overall_progress = 100

            await self.emit_event(
                AgentPhase.COMPLETED,
                "End-to-end AI News Video Generation workflow complete. All stories ready for broadcast.",
                progress=100,
            )

            return global_state.world_stories, global_state.india_stories

        except Exception as e:
            logger.error(f"Orchestrator pipeline failed: {e}", exc_info=True)
            global_state.is_running = False
            global_state.active_phase = AgentPhase.FAILED
            await self.emit_event(
                AgentPhase.FAILED,
                f"Orchestrator encountered an unhandled exception: {str(e)}",
                progress=0,
            )
            return global_state.world_stories, global_state.india_stories

    async def process_story_full(self, story: NewsStory) -> NewsStory:
        """Executes the full pipeline for a single news story:
        Script + Image -> Voice -> Video Assembly -> QC Audit.
        """
        try:
            # 1. Script Generation Agent
            await self.emit_event(
                AgentPhase.SCRIPT_GENERATION,
                f"Drafting authoritative 5-min broadcast script for '{story.title}'",
                story=story,
            )
            await self.script_agent.generate_script(story)

            # 2. Pipelined Concurrent Tracks: Visual Assets & Voice Narration
            async def _run_visual_track():
                await self.image_agent.process_story_images(story)
                await self.emit_event(
                    AgentPhase.IMAGE_TO_VIDEO,
                    f"Converting news images into animated video clips via MiniMaxAI/MiniMax-H3 for '{story.title}'",
                    story=story,
                )
                await self.image_to_video_agent.convert_images_to_video_clips(story)

            async def _run_voice_track():
                await self.emit_event(
                    AgentPhase.VOICE_GENERATION,
                    f"Synthesizing broadcast audio track for '{story.title}'",
                    story=story,
                )
                await self.voice_agent.generate_voice(story)

            # Run visual processing and voice synthesis concurrently
            await asyncio.gather(_run_visual_track(), _run_voice_track())

            # 3. Video Assembly Agent (FFmpeg with GPU acceleration & instant stream copy)
            await self.emit_event(
                AgentPhase.VIDEO_ASSEMBLY,
                f"Assembling 16:9 news video with audio timeline for '{story.title}'",
                story=story,
            )
            await self.video_assembler.render_video(story)


            # 4. Quality Control Agent
            await self.emit_event(
                AgentPhase.QUALITY_CONTROL,
                f"Running automated QC audit on '{story.title}'",
                story=story,
            )
            passed, notes = await self.qc_agent.audit_story(story)

            if not passed:
                logger.warning(f"QC audit requested retry for story {story.id}: {notes}")
                # One automatic retry for video assembly if needed
                await self.video_assembler.render_video(story)
                passed, notes = await self.qc_agent.audit_story(story)

            global_state.register_story(story)
            return story

        except Exception as e:
            logger.error(f"Error processing story {story.id}: {e}", exc_info=True)
            story.status = AgentPhase.FAILED
            story.status_message = f"Error: {str(e)}"
            global_state.register_story(story)
            await self.emit_event(
                AgentPhase.FAILED,
                f"Processing failed for '{story.title}': {str(e)}",
                story=story,
            )
            return story
