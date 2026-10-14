import asyncio
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from ..base import NewsStory, Region, PipelineEvent, AgentPhase


class PipelineState(BaseModel):
    """Global state registry for the multi-agent video generation pipeline."""
    is_running: bool = False
    active_phase: AgentPhase = AgentPhase.ORCHESTRATOR
    overall_progress: int = 0
    world_stories: List[NewsStory] = Field(default_factory=list)
    india_stories: List[NewsStory] = Field(default_factory=list)
    story_map: Dict[str, NewsStory] = Field(default_factory=dict)
    event_history: List[PipelineEvent] = Field(default_factory=list)

    def register_story(self, story: NewsStory):
        self.story_map[story.id] = story
        if story.region == Region.INDIA:
            # Replace if already exists or append
            self.india_stories = [s for s in self.india_stories if s.id != story.id] + [story]
            self.india_stories.sort(key=lambda x: x.rank)
        else:
            self.world_stories = [s for s in self.world_stories if s.id != story.id] + [story]
            self.world_stories.sort(key=lambda x: x.rank)

    def get_all_stories(self) -> List[NewsStory]:
        return list(self.story_map.values())


class PipelineBroadcaster:
    """Manages Server-Sent Events (SSE) broadcast subscribers."""

    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def broadcast(self, event: PipelineEvent):
        for q in list(self._subscribers):
            try:
                await q.put(event)
            except Exception:
                pass


# Global singleton instances
global_state = PipelineState()
global_broadcaster = PipelineBroadcaster()
