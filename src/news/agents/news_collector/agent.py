import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Tuple
from ..base import NewsStory, Region, AgentPhase
from ...config import settings
from ...tools.news_fetcher import fetch_news_for_region
from .ranker import NewsRanker

logger = logging.getLogger(__name__)


class NewsCollectionAgent:
    """Agent responsible for:
    1. Fetching raw candidate feeds from trusted sources.
    2. Enforcing strict 24h freshness filter & deduplication.
    3. Selecting and ranking the Top 2 World News and Top 2 India News stories.
    """

    def __init__(self):
        self.ranker = NewsRanker()

    async def collect_pipeline(self) -> Tuple[List[NewsStory], List[NewsStory]]:
        """Collects candidate stories and selects Top World and India stories in parallel."""
        logger.info(f"NewsCollectionAgent: Initiating parallel retrieval for Top {settings.TOP_STORIES_PER_REGION} World and India stories...")
        world_task = self.collect_for_region(Region.WORLDWIDE)
        india_task = self.collect_for_region(Region.INDIA)

        world_stories, india_stories = await asyncio.gather(world_task, india_task)
        return world_stories, india_stories

    async def collect_for_region(self, region: Region) -> List[NewsStory]:
        """Fetch candidates, apply 24h filtering, and rank Top 5 stories for a specific region."""
        # 1. Ingest feeds with 24-hour freshness filter
        candidates = await fetch_news_for_region(region=region, max_age_hours=24.0, max_candidates=25)
        logger.info(f"NewsCollectionAgent: Found {len(candidates)} fresh candidate articles for {region.value}")

        # 2. Select & Rank Top 5 using Gemini/LLM
        ranked_items = await self.ranker.rank_and_select(candidates, region)

        # 3. Build NewsStory objects
        stories = []
        limit = settings.TOP_STORIES_PER_REGION
        for item in ranked_items[:limit]:
            story = NewsStory(
                region=region,
                rank=item["rank"],
                title=item["title"],
                summary=item["summary"],
                url=item["url"],
                source=item["source"],
                published_at=datetime.now(timezone.utc),
                category=item.get("category", "General"),
                status=AgentPhase.NEWS_COLLECTION,
                progress_pct=100,
                status_message="Curated & Clustered across verified wire sources",
                candidate_image_urls=item.get("image_urls", []),
                sources_clustered=item.get("sources_clustered", [item["source"]]),
            )
            stories.append(story)

        return stories
