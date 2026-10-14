from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, HttpUrl


class Region(str, Enum):
    WORLDWIDE = "WORLDWIDE"
    INDIA = "INDIA"


class NewsArticle(BaseModel):
    """Pydantic enterprise schema for a validated news article."""
    title: str = Field(description="Headline of the news article")
    source: str = Field(description="Originating news outlet or publication")
    url: str = Field(description="Direct URL to the news article")
    published_at: str = Field(description="Publication timestamp (ISO 8601 or parsed human-readable string)")
    published_timestamp: Optional[float] = Field(default=None, description="Unix timestamp in UTC")
    age_hours: Optional[float] = Field(default=None, description="Age in hours relative to report generation")
    summary: str = Field(description="Concise 1-2 sentence executive summary of the story")
    region: Region = Field(description="Region category: WORLDWIDE or INDIA")
    category: str = Field(default="General", description="Topical category (e.g. Geopolitics, Technology, Economy, Science)")
    key_points: List[str] = Field(default_factory=list, description="Key bullet highlights")


class TopNewsReport(BaseModel):
    """Enterprise report aggregating top 5 worldwide and top 5 India news stories."""
    report_date: str = Field(description="Calendar date of the report (YYYY-MM-DD)")
    generated_at: str = Field(description="Generation timestamp in UTC")
    worldwide_news: List[NewsArticle] = Field(description="Top 5 verified worldwide news articles within last 24h")
    india_news: List[NewsArticle] = Field(description="Top 5 verified India news articles within last 24h")
    llm_provider_used: str = Field(description="Model and provider that curated and summarized the report")
    fallback_occurred: bool = Field(default=False, description="Whether fallback model was activated")
    execution_time_seconds: Optional[float] = Field(default=None, description="Total execution time in seconds")
