import asyncio
from datetime import datetime, timezone
from pathlib import Path

from news.agents.base import NewsStory, Region, AgentPhase
from news.agents.script_agent import NewsScriptAgent
from news.agents.image_agent import ImageResearchAgent
from news.agents.voice_agent import VoiceGenerationAgent
from news.agents.video_assembler import VideoAssemblyAgent
from news.agents.quality_control import QualityControlAgent


async def test_end_to_end_single_story_pipeline():
    """Verify that a news story passes through Script, Image, Voice, Assembly, and QC successfully."""
    # 1. Mock fresh story
    story = NewsStory(
        region=Region.WORLDWIDE,
        rank=1,
        title="Global Fusion Energy Milestone Achieved with Net Power Output",
        summary="International researchers announced a historic breakthrough in commercial fusion energy after achieving sustained net positive power for over 20 minutes.",
        url="https://news.google.com",
        source="Reuters Science",
        published_at=datetime.now(timezone.utc),
        category="Tech",
    )

    # 2. Script Agent
    script_agent = NewsScriptAgent()
    script = await script_agent.generate_script(story)
    assert script is not None
    assert len(script.segments) == 6
    assert story.status == AgentPhase.SCRIPT_GENERATION

    # 3. Image Research Agent
    image_agent = ImageResearchAgent()
    images = await image_agent.process_story_images(story)
    assert len(images) >= 1
    for p in images:
        assert Path(p).exists()
    assert story.status == AgentPhase.IMAGE_RESEARCH

    # 4. Voice Generation Agent
    voice_agent = VoiceGenerationAgent()
    audio_path, duration = await voice_agent.generate_voice(story)
    assert Path(audio_path).exists()
    assert duration > 2.0
    assert story.status == AgentPhase.VOICE_GENERATION

    # 5. Video Assembly Agent (FFmpeg)
    video_assembler = VideoAssemblyAgent()
    video_path = await video_assembler.render_video(story)
    assert Path(video_path).exists()
    assert Path(video_path).stat().st_size > 10000
    assert story.status == AgentPhase.VIDEO_ASSEMBLY

    # 6. Quality Control Agent
    qc_agent = QualityControlAgent()
    passed, notes = await qc_agent.audit_story(story)
    assert passed is True
    assert story.status == AgentPhase.COMPLETED
    assert story.media.qc_passed is True
    print(f"Test Story Pipeline Passed: Video at {video_path}, Duration: {duration:.1f}s")


if __name__ == "__main__":
    asyncio.run(test_end_to_end_single_story_pipeline())
