import json
import logging
from typing import List, Dict, Any
from ..llm_factory import MultiProviderLLM
from ..base import Region
from ...config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Senior Executive Editor and News Ranking Specialist for an AI News Video Broadcasting Network.
Your task is to analyze raw candidate news stories and select the top high-significance stories published in the past 24 hours.

Rules:
1. Select the top highest impact stories (geopolitical, tech, economy, major science, critical public interest).
2. Eliminate duplicate angles, clickbait, or trivial stories.
3. Assign a primary category: World, Politics, Economy, Tech, Security, Environment, Society.
4. Single-Topic Headline Hygiene: If a candidate headline is a composite morning newsletter digest combining multiple topics (e.g., 'Military attack and celebrity update: Morning Rundown'), CLEAN the title to cover ONLY the single primary serious news event (e.g., 'U.S. Marines injured in Iran attack'). Never mix entertainment gossip into hard news stories. Remove all digest tags like 'Morning Rundown' or '5 things to know'.
5. Output MUST be valid JSON adhering strictly to this schema:
[
  {
    "rank": 1,
    "title": "Clear, objective, high-impact headline",
    "summary": "2-3 sentence executive brief summarizing the core event and why it is critical right now.",
    "category": "Tech",
    "original_index": 0
  },
  ...
]
Do not include any markdown wrappers other than ```json or plain JSON.
"""


def cluster_candidate_articles(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cluster overlapping candidate news articles covering the exact same event into multi-source dossiers."""
    import re
    stop_words = {"the", "a", "an", "in", "on", "of", "and", "to", "for", "with", "at", "by", "from", "is", "are", "after", "as", "new", "over"}

    def extract_keywords(text: str) -> set:
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        return {w for w in words if w not in stop_words}

    clustered = []
    consumed = set()

    for i, c in enumerate(candidates):
        if i in consumed:
            continue
        base_item = dict(c)
        base_kw = extract_keywords(c.get("title", ""))
        matched_sources = [c.get("source", "Wire Service")]
        combined_summaries = [c.get("summary", "")]

        for j, other in enumerate(candidates[i + 1:], start=i + 1):
            if j in consumed:
                continue
            other_kw = extract_keywords(other.get("title", ""))
            overlap = len(base_kw & other_kw)
            if overlap >= 3:
                consumed.add(j)
                src = other.get("source", "")
                if src and src not in matched_sources:
                    matched_sources.append(src)
                s_text = other.get("summary", "").strip()
                if s_text and s_text not in combined_summaries:
                    combined_summaries.append(s_text)
                for u in other.get("image_urls", []):
                    if u not in base_item.get("image_urls", []):
                        base_item.setdefault("image_urls", []).append(u)

        base_item["sources_clustered"] = matched_sources
        if len(matched_sources) > 1:
            base_item["source"] = f"{matched_sources[0]} (+{len(matched_sources)-1} sources)"
            base_item["summary"] = " ".join(combined_summaries[:2])
        clustered.append(base_item)

    return clustered


class NewsRanker:
    """Uses Gemini 3.8 Flash to select and rank top stories."""

    def __init__(self):
        self.llm = MultiProviderLLM(primary_model=settings.NEWS_RESEARCH_MODEL)

    async def rank_and_select(
        self, candidates: List[Dict[str, Any]], region: Region
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        # Deduplicate and cluster multi-outlet coverage of identical events
        candidates = cluster_candidate_articles(candidates)

        limit = settings.TOP_STORIES_PER_REGION

        # If candidates <= limit, return them directly
        if len(candidates) <= limit:
            ranked = []
            for i, c in enumerate(candidates, 1):
                item = dict(c)
                item["rank"] = i
                item["category"] = "General"
                ranked.append(item)
            return ranked

        # Prepare payload for LLM
        candidate_summary = []
        for idx, c in enumerate(candidates[:20]):
            candidate_summary.append({
                "index": idx,
                "title": c["title"],
                "source": c["source"],
                "age_hours": c.get("age_hours", 0),
                "snippet": c.get("summary", "")[:250],
            })

        prompt = (
            f"Region: {region.value}\n"
            f"Candidate Articles (last 24 hours):\n{json.dumps(candidate_summary, indent=2)}\n\n"
            f"Select and rank the Top {limit} most critical stories for broadcast."
        )

        try:
            raw_response, model_used, _ = await self.llm.generate(SYSTEM_PROMPT, prompt)
            clean_text = raw_response.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            parsed = json.loads(clean_text.strip())
            results = []
            for entry in parsed[:limit]:
                orig_idx = entry.get("original_index", 0)
                base = candidates[orig_idx] if 0 <= orig_idx < len(candidates) else candidates[0]
                results.append({
                    "rank": entry.get("rank", len(results) + 1),
                    "title": entry.get("title", base["title"]),
                    "summary": entry.get("summary", base["summary"]),
                    "category": entry.get("category", "General"),
                    "source": base["source"],
                    "url": base["url"],
                    "published_at": base.get("published_at"),
                    "image_urls": base.get("image_urls", []),
                    "sources_clustered": base.get("sources_clustered", [base["source"]]),
                })
            return results
        except Exception as e:
            logger.warning(f"LLM ranking failed ({e}), falling back to chronological recency ranking")
            results = []
            for i, c in enumerate(candidates[:limit], 1):
                results.append({
                    "rank": i,
                    "title": c["title"],
                    "summary": c["summary"],
                    "category": "Breaking",
                    "source": c["source"],
                    "url": c["url"],
                    "published_at": c.get("published_at"),
                    "image_urls": c.get("image_urls", []),
                    "sources_clustered": c.get("sources_clustered", [c["source"]]),
                })
            return results
