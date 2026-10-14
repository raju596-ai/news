import json
import logging
import time
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

from langgraph.graph import StateGraph, START, END

from .state import NewsAgentState
from .llm_factory import llm_service
from ..models.article import NewsArticle, TopNewsReport, Region
from ..tools.news_fetcher import fetch_news_for_region
from ..tools.date_utils import get_today_date_str, is_within_last_24_hours, parse_datetime

logger = logging.getLogger(__name__)


class NewsRetrievalAgent:
    """LangGraph-powered Single Agent for real-time news retrieval.
    
    Retrieves Top 5 Worldwide and Top 5 India news stories published within the last 24 hours.
    Primary LLM: Gemini (gemini-3.8-flash)
    Fallback LLM: Groq (llama-3.1-8b-instant / openai/gpt-oss-120b)
    """

    def __init__(self):
        self.workflow = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(NewsAgentState)

        # Register nodes
        graph.add_node("fetch_feeds", self._fetch_feeds_node)
        graph.add_node("validate_freshness", self._validate_freshness_node)
        graph.add_node("curate_and_rank", self._curate_and_rank_node)

        # Wire workflow edges
        graph.add_edge(START, "fetch_feeds")
        graph.add_edge("fetch_feeds", "validate_freshness")
        graph.add_edge("validate_freshness", "curate_and_rank")
        graph.add_edge("curate_and_rank", END)

        return graph.compile()

    async def _fetch_feeds_node(self, state: NewsAgentState) -> Dict[str, Any]:
        """Node 1: Fetch raw real-time feed candidates for Worldwide and India."""
        logs = list(state.get("logs", []))
        logs.append(f"[{datetime.now(timezone.utc).isoformat()}] Starting news feed ingestion...")

        # Fetch in parallel
        import asyncio
        ww_task = fetch_news_for_region(Region.WORLDWIDE, max_age_hours=24.0)
        in_task = fetch_news_for_region(Region.INDIA, max_age_hours=24.0)
        raw_ww, raw_in = await asyncio.gather(ww_task, in_task)

        logs.append(f"Retrieved {len(raw_ww)} worldwide candidate articles.")
        logs.append(f"Retrieved {len(raw_in)} India candidate articles.")

        return {
            "raw_worldwide": raw_ww,
            "raw_india": raw_in,
            "logs": logs,
        }

    async def _validate_freshness_node(self, state: NewsAgentState) -> Dict[str, Any]:
        """Node 2: Strict 24-hour verification against current UTC timestamp."""
        logs = list(state.get("logs", []))
        now_utc = datetime.now(timezone.utc)
        logs.append(f"Validating article freshness against current UTC time: {now_utc.isoformat()}")

        validated_ww = []
        for item in state.get("raw_worldwide", []):
            dt = parse_datetime(item.get("published_at"))
            is_valid, age = is_within_last_24_hours(dt, max_hours=24.0, reference_time=now_utc)
            if is_valid:
                item["age_hours"] = age
                validated_ww.append(item)

        validated_in = []
        for item in state.get("raw_india", []):
            dt = parse_datetime(item.get("published_at"))
            is_valid, age = is_within_last_24_hours(dt, max_hours=24.0, reference_time=now_utc)
            if is_valid:
                item["age_hours"] = age
                validated_in.append(item)

        logs.append(f"Validated {len(validated_ww)} worldwide items within 24h.")
        logs.append(f"Validated {len(validated_in)} India items within 24h.")

        return {
            "validated_worldwide": validated_ww,
            "validated_india": validated_in,
            "logs": logs,
        }

    async def _curate_and_rank_node(self, state: NewsAgentState) -> Dict[str, Any]:
        """Node 3: Use LLM to analyze, deduplicate, select Top 5, and generate executive summaries."""
        logs = list(state.get("logs", []))
        today_date = get_today_date_str()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Select top 8 freshest candidates per region and compact fields to minimize token usage
        def _compact_candidates(items):
            compacted = []
            for it in items[:8]:
                compacted.append({
                    "title": it.get("title"),
                    "source": it.get("source"),
                    "published_at": it.get("published_at"),
                    "summary": (it.get("summary") or "")[:180],
                    "url": it.get("url"),
                })
            return compacted

        ww_candidates = _compact_candidates(state.get("validated_worldwide", []))
        in_candidates = _compact_candidates(state.get("validated_india", []))

        system_prompt = (
            "You are an enterprise-grade Senior News Editor and Intelligence Analyst. "
            "Your task is to review candidate news articles from the last 24 hours and select "
            "the TOP 5 most critical, high-impact stories for WORLDWIDE and TOP 5 for INDIA.\n\n"
            "Requirements:\n"
            "1. Strictly output valid JSON adhering to the specified schema.\n"
            "2. Select exactly 5 distinct, high-impact stories for Worldwide and 5 for India.\n"
            "3. Write a high-quality, factual 1-2 sentence executive summary for each story.\n"
            "4. Provide 2-3 key bullet points per story.\n"
            "5. Assign a relevant topical category (e.g. Geopolitics, Technology, Economy, Science, Governance).\n"
            "6. Preserve original URL, source, and published_at timestamp."
        )

        user_prompt = f"""
Current Real-Time Reference Date: {today_date} (UTC: {now_iso})

CANDIDATE WORLDWIDE NEWS (Last 24 Hours):
{json.dumps(ww_candidates, indent=2)}

CANDIDATE INDIA NEWS (Last 24 Hours):
{json.dumps(in_candidates, indent=2)}

Output strictly valid JSON in this structure:
{{
  "worldwide": [
    {{
      "title": "...",
      "source": "...",
      "url": "...",
      "published_at": "...",
      "summary": "...",
      "category": "...",
      "key_points": ["...", "..."]
    }}
  ],
  "india": [
    {{
      "title": "...",
      "source": "...",
      "url": "...",
      "published_at": "...",
      "summary": "...",
      "category": "...",
      "key_points": ["...", "..."]
    }}
  ]
}}
"""

        logs.append("Submitting candidate pool to LLM service...")
        response_text, model_used, fallback = await llm_service.generate(system_prompt, user_prompt)
        logs.append(f"LLM completed generation using: {model_used} (Fallback activated: {fallback})")

        # Parse JSON from response
        try:
            # Extract JSON block if surrounded by markdown fences
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if json_match:
                cleaned_json = json_match.group(1)
            else:
                cleaned_json = response_text.strip()
            
            parsed = json.loads(cleaned_json)
        except Exception as e:
            logs.append(f"JSON parsing warning: {e}. Attempting fallback parser.")
            parsed = {"worldwide": [], "india": []}

        # Transform to Pydantic models
        ww_articles: List[NewsArticle] = []
        for a in parsed.get("worldwide", [])[:5]:
            try:
                ww_articles.append(NewsArticle(
                    title=a.get("title", ""),
                    source=a.get("source", "Global Source"),
                    url=a.get("url", ""),
                    published_at=a.get("published_at", now_iso),
                    summary=a.get("summary", ""),
                    region=Region.WORLDWIDE,
                    category=a.get("category", "General"),
                    key_points=a.get("key_points", []),
                ))
            except Exception as err:
                logger.warning(f"Error parsing article: {err}")

        # Fallback if LLM returned fewer than 5
        if len(ww_articles) < 5:
            for item in ww_candidates:
                if not any(a.title == item["title"] for a in ww_articles):
                    ww_articles.append(NewsArticle(
                        title=item["title"],
                        source=item["source"],
                        url=item["url"],
                        published_at=item["published_at"],
                        summary=item["summary"],
                        region=Region.WORLDWIDE,
                        category="General",
                        key_points=[item["summary"]],
                    ))
                if len(ww_articles) >= 5:
                    break

        in_articles: List[NewsArticle] = []
        for a in parsed.get("india", [])[:5]:
            try:
                in_articles.append(NewsArticle(
                    title=a.get("title", ""),
                    source=a.get("source", "India Source"),
                    url=a.get("url", ""),
                    published_at=a.get("published_at", now_iso),
                    summary=a.get("summary", ""),
                    region=Region.INDIA,
                    category=a.get("category", "National"),
                    key_points=a.get("key_points", []),
                ))
            except Exception as err:
                logger.warning(f"Error parsing India article: {err}")

        # Fallback if LLM returned fewer than 5
        if len(in_articles) < 5:
            for item in in_candidates:
                if not any(a.title == item["title"] for a in in_articles):
                    in_articles.append(NewsArticle(
                        title=item["title"],
                        source=item["source"],
                        url=item["url"],
                        published_at=item["published_at"],
                        summary=item["summary"],
                        region=Region.INDIA,
                        category="National",
                        key_points=[item["summary"]],
                    ))
                if len(in_articles) >= 5:
                    break

        report = TopNewsReport(
            report_date=today_date,
            generated_at=now_iso,
            worldwide_news=ww_articles[:5],
            india_news=in_articles[:5],
            llm_provider_used=model_used,
            fallback_occurred=fallback,
        )

        return {
            "final_report": report,
            "llm_provider_used": model_used,
            "fallback_occurred": fallback,
            "logs": logs,
        }

    async def run(self) -> TopNewsReport:
        """Run the complete agent workflow and return TopNewsReport."""
        start_time = time.time()
        initial_state: NewsAgentState = {
            "task": "Retrieve Top 5 Worldwide and Top 5 India news within last 24h",
            "target_date": get_today_date_str(),
            "reference_timestamp": datetime.now(timezone.utc).isoformat(),
            "max_age_hours": 24.0,
            "logs": [],
        }

        final_state = await self.workflow.ainvoke(initial_state)
        report: TopNewsReport = final_state["final_report"]
        report.execution_time_seconds = round(time.time() - start_time, 2)
        return report

    async def run_stream(self):
        """Execute agent workflow yielding progress events for SSE or UI consumption."""
        start_time = time.time()
        initial_state: NewsAgentState = {
            "task": "Retrieve Top 5 Worldwide and Top 5 India news within last 24h",
            "target_date": get_today_date_str(),
            "reference_timestamp": datetime.now(timezone.utc).isoformat(),
            "max_age_hours": 24.0,
            "logs": [],
        }

        yield {
            "event": "start",
            "step": 0,
            "message": "Initializing Real-Time News Intelligence Agent...",
            "details": f"Target Date: {initial_state['target_date']} | Temporal Window: 24 Hours",
            "progress": 10,
        }

        async for chunk in self.workflow.astream(initial_state):
            for node_name, node_state in chunk.items():
                if node_name == "fetch_feeds":
                    ww_count = len(node_state.get("raw_worldwide", []))
                    in_count = len(node_state.get("raw_india", []))
                    yield {
                        "event": "step",
                        "step": 1,
                        "node": "fetch_feeds",
                        "message": f"Ingested {ww_count} Global and {in_count} India live feed candidates.",
                        "details": "Sources: Google News Worldwide, BBC News, The Hindu, NDTV...",
                        "progress": 35,
                        "stats": {"raw_worldwide": ww_count, "raw_india": in_count},
                    }
                elif node_name == "validate_freshness":
                    ww_val = len(node_state.get("validated_worldwide", []))
                    in_val = len(node_state.get("validated_india", []))
                    yield {
                        "event": "step",
                        "step": 2,
                        "node": "validate_freshness",
                        "message": f"Verified {ww_val + in_val} candidate articles published within last 24 hours.",
                        "details": "Strict UTC timestamp filtering passed. Stale articles discarded.",
                        "progress": 65,
                        "stats": {"validated_worldwide": ww_val, "validated_india": in_val},
                    }
                elif node_name == "curate_and_rank":
                    report: TopNewsReport = node_state.get("final_report")
                    if report:
                        report.execution_time_seconds = round(time.time() - start_time, 2)
                    yield {
                        "event": "complete",
                        "step": 3,
                        "node": "curate_and_rank",
                        "message": "AI executive curation complete! Intelligence report compiled.",
                        "details": f"Curated via {node_state.get('llm_provider_used', 'AI Model')} in {round(time.time() - start_time, 2)}s",
                        "progress": 100,
                        "report": report.model_dump() if report else None,
                    }

