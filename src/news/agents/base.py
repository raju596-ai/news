"""Base models, interfaces, and event schemas for the Multi-Agent News Video System."""

import uuid
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Region(str, Enum):
    WORLDWIDE = "WORLDWIDE"
    INDIA = "INDIA"


class AgentPhase(str, Enum):
    ORCHESTRATOR = "ORCHESTRATOR"
    NEWS_COLLECTION = "NEWS_COLLECTION"
    SCRIPT_GENERATION = "SCRIPT_GENERATION"
    IMAGE_RESEARCH = "IMAGE_RESEARCH"
    IMAGE_TO_VIDEO = "IMAGE_TO_VIDEO"
    VOICE_GENERATION = "VOICE_GENERATION"
    VIDEO_ASSEMBLY = "VIDEO_ASSEMBLY"
    QUALITY_CONTROL = "QUALITY_CONTROL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScriptSegment(BaseModel):
    """One of the 6 core beats in the news script."""
    beat: str  # "Hook", "What Happened", "Key Details", "Why It Matters", "Current Status", "Closing"
    narration: str
    visual_cue: str
    estimated_duration_sec: float = 15.0
    image_path: Optional[str] = None
    video_clip_path: Optional[str] = None


class StoryScript(BaseModel):
    """Full structured script for a news story."""
    story_id: str
    headline: str
    hook: str
    what_happened: str
    key_details: str
    why_it_matters: str
    latest_update: str = ""
    current_status: str = ""
    closing: str
    segments: List[ScriptSegment] = Field(default_factory=list)
    total_words: int = 0
    estimated_seconds: float = 300.0


class StoryMedia(BaseModel):
    """Media assets generated for a news story."""
    image_paths: List[str] = Field(default_factory=list)
    video_clip_paths: List[str] = Field(default_factory=list)
    audio_path: Optional[str] = None
    audio_duration_sec: float = 0.0
    video_path: Optional[str] = None
    vertical_video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    thumbnail_b_path: Optional[str] = None
    subtitles_path: Optional[str] = None
    metadata_path: Optional[str] = None
    qc_passed: bool = False
    qc_notes: List[str] = Field(default_factory=list)



class NewsStory(BaseModel):
    """Full story entity tracked across all pipeline stages."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    region: Region
    rank: int  # 1 to 5
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    category: str = "General"
    language: str = "en"  # "en", "te" (Telugu), "hi" (Hindi)
    aspect_ratio: str = "16:9"  # "16:9", "9:16", "both"
    status: AgentPhase = AgentPhase.NEWS_COLLECTION
    progress_pct: int = 0
    status_message: str = "Discovered"

    script: Optional[StoryScript] = None
    media: StoryMedia = Field(default_factory=StoryMedia)
    candidate_image_urls: List[str] = Field(default_factory=list)
    sources_clustered: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineEvent(BaseModel):
    """Real-time event for SSE streaming to UI."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stage: AgentPhase
    story_id: Optional[str] = None
    story_title: Optional[str] = None
    region: Optional[Region] = None
    message: str
    progress: int = 0
    data: Optional[Dict[str, Any]] = None
