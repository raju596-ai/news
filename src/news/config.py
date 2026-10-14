import os
import shutil
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Explicitly load .env file from project root
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


def resolve_ffmpeg_path() -> str:
    """Find installed ffmpeg binary on system or fallback to PATH."""
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path

    # Check common Windows winget installation paths
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        winget_pattern = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pattern.exists():
            for p in winget_pattern.glob("**/ffmpeg.exe"):
                if p.is_file():
                    return str(p)

    return "ffmpeg"


def resolve_intro_video_path() -> Path:
    """Find intro prefix video clip (prioritizing D:\\news\\data\\start.mp4)."""
    env_val = os.getenv("INTRO_VIDEO_PATH")
    if env_val:
        p = Path(env_val).resolve()
        if p.is_file():
            return p
    candidates = [
        ROOT_DIR / "data" / "start.mp4",
        ROOT_DIR / "data" / "intro.mp4",
        ROOT_DIR / "introend" / "start.mp4",
        ROOT_DIR / "introend" / "intro.mp4",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return ROOT_DIR / "data" / "start.mp4"


def resolve_end_video_path() -> Path:
    """Find ending suffix video clip (prioritizing D:\\news\\data\\end.mp4)."""
    env_val = os.getenv("END_VIDEO_PATH")
    if env_val:
        p = Path(env_val).resolve()
        if p.is_file():
            return p
    candidates = [
        ROOT_DIR / "data" / "end.mp4",
        ROOT_DIR / "introend" / "end.mp4",
        ROOT_DIR / "data" / "ending.mp4",
        ROOT_DIR / "introend" / "ending.mp4",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return ROOT_DIR / "data" / "end.mp4"


class Settings(BaseSettings):
    """Enterprise configuration settings for AI News Video Generation Platform."""

    # API Keys
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GROQ_API_KEY: str = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    HUGGING_API_KEY: str = Field(default_factory=lambda: os.getenv("HUGGING_API_KEY", ""))
    HF_TOKEN: str = Field(default_factory=lambda: os.getenv("HF_TOKEN", os.getenv("HUGGING_API_KEY", "")))
    NVIDIA_API_KEY: str = Field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", ""))

    # NVIDIA NIM & GenAI Endpoints
    NVIDIA_GENAI_BASE_URL: str = "https://ai.api.nvidia.com/v1/genai"
    NVIDIA_INTEGRATE_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_IMAGE_MODEL: str = "black-forest-labs/flux.2-klein-4b"
    NVIDIA_IMAGE_MODEL_FALLBACK: str = "black-forest-labs/flux.1-dev"
    NVIDIA_IMAGE_MODEL_TURBO: str = "black-forest-labs/flux.1-schnell"
    NVIDIA_IMAGE_MODEL_BALANCED: str = "black-forest-labs/flux.2-klein-4b"
    NVIDIA_IMAGE_MODEL_PRO: str = "black-forest-labs/flux.1-dev"
    NVIDIA_VISION_MODEL: str = "meta/llama-3.2-11b-vision-instruct"

    # Agent Specific Models
    ORCHESTRATOR_MODEL: str = "openai/gpt-oss-120b"
    NEWS_RESEARCH_MODEL: str = "gemini-2.5-flash"  # Primary for news research/ranking
    SCRIPT_MODEL: str = "openai/gpt-oss-120b"  # Groq 120B / Llama 70B
    IMAGE_AGENT_MODEL: str = "gemini-2.5-flash"  # Multimodal verification
    IMAGE_TO_VIDEO_MODEL: str = "MiniMaxAI/MiniMax-H3"
    TTS_MODEL_GEMINI: str = "gemini-2.5-flash-preview-tts"
    QC_MODEL: str = "openai/gpt-oss-20b"  # Fast validation

    # Fallback LLM Models
    PRIMARY_PROVIDER: str = "gemini"
    PRIMARY_MODEL: str = "gemini-2.5-flash"
    GEMINI_FALLBACK_MODEL: str = "gemini-2.0-flash"
    GEMINI_TERTIARY_MODEL: str = "gemini-1.5-flash"
    FALLBACK_PROVIDER: str = "groq"
    FALLBACK_MODEL_GROQ: str = "openai/gpt-oss-20b"
    FALLBACK_MODEL_GROQ_SECONDARY: str = "openai/gpt-oss-120b"

    # News freshness settings
    MAX_NEWS_AGE_HOURS: int = 24
    TOP_STORIES_PER_REGION: int = 2

    # Storage & Media Paths
    STORAGE_DIR: Path = ROOT_DIR / "storage"
    MEDIA_DIR: Path = STORAGE_DIR / "media"
    FFMPEG_PATH: str = Field(default_factory=resolve_ffmpeg_path)

    # Intro & Ending Video Clips (Prefix & Suffix)
    INTRO_VIDEO_PATH: Path = Field(default_factory=resolve_intro_video_path)
    END_VIDEO_PATH: Path = Field(default_factory=resolve_end_video_path)

    def get_intro_video_path(self) -> Optional[Path]:
        """Dynamically return the existing intro video path, or None if not found."""
        candidates = [
            self.INTRO_VIDEO_PATH,
            ROOT_DIR / "data" / "start.mp4",
            ROOT_DIR / "data" / "intro.mp4",
            ROOT_DIR / "introend" / "start.mp4",
            ROOT_DIR / "introend" / "intro.mp4",
        ]
        for c in candidates:
            if c:
                p = Path(c).resolve()
                if p.is_file():
                    return p
        return None

    def get_end_video_path(self) -> Optional[Path]:
        """Dynamically return the existing end video path, or None if not found."""
        candidates = [
            self.END_VIDEO_PATH,
            ROOT_DIR / "data" / "end.mp4",
            ROOT_DIR / "introend" / "end.mp4",
            ROOT_DIR / "data" / "ending.mp4",
            ROOT_DIR / "introend" / "ending.mp4",
        ]
        for c in candidates:
            if c:
                p = Path(c).resolve()
                if p.is_file():
                    return p
        return None

    # YouTube Standard Video Specs (1080p Full HD, 16:9, 30 FPS, AAC 48kHz)
    VIDEO_WIDTH: int = 1920
    VIDEO_HEIGHT: int = 1080
    VERTICAL_VIDEO_WIDTH: int = 1080
    VERTICAL_VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30
    AUDIO_SAMPLE_RATE: int = 48000
    AUDIO_BITRATE: str = "192k"

    # Default Language & Multilingual Vernacular Voice Config
    DEFAULT_LANGUAGE: str = "en"
    VOICE_WORLD_ANCHOR: str = "en-US-ChristopherNeural"
    VOICE_WORLD_REPORTER: str = "en-US-JennyNeural"
    VOICE_INDIA_ANCHOR: str = "en-IN-PrabhatNeural"
    VOICE_INDIA_REPORTER: str = "en-IN-NeerjaNeural"
    VOICE_TELUGU_ANCHOR: str = "te-IN-MohanNeural"
    VOICE_TELUGU_REPORTER: str = "te-IN-ShrutiNeural"
    VOICE_HINDI_ANCHOR: str = "hi-IN-MadhurNeural"
    VOICE_HINDI_REPORTER: str = "hi-IN-SwaraNeural"

    # Server settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Ensure Hugging Face token is set if only HUGGING_API_KEY was provided
if settings.HUGGING_API_KEY and not os.getenv("HF_TOKEN"):
    os.environ["HF_TOKEN"] = settings.HUGGING_API_KEY
