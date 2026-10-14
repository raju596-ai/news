import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import feedparser
import httpx
from bs4 import BeautifulSoup
from .date_utils import parse_datetime, is_within_last_24_hours
from ..models.article import Region

logger = logging.getLogger(__name__)

# Curated high-reliability RSS feeds for real-time news
FEEDS_WORLDWIDE = [
    {
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "default_source": "Google News World",
    },
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "default_source": "BBC News",
    },
    {
        "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "default_source": "Google News Global",
    },
]

FEEDS_INDIA = [
    {
        "url": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
        "default_source": "Google News India",
    },
    {
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "default_source": "The Hindu",
    },
    {
        "url": "https://feeds.feedburner.com/ndtvnews-india-news",
        "default_source": "NDTV",
    },
    {
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en",
        "default_source": "Google News India National",
    },
]


def clean_html(raw_html: str) -> str:
    """Remove HTML tags and entities from summary/description."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    # Remove repeated whitespaces
    return re.sub(r"\s+", " ", text).strip()


def sanitize_news_headline(title: str) -> str:
    """Clean and sanitize news headlines, eliminating digest tags and mixed-topic roundup filler."""
    if not title:
        return ""

    t = title.strip()

    # 1. Remove trailing source tags: " - NBC News", " | BBC", " - Reuters"
    t = re.sub(r"\s+[-|]\s+[A-Za-z0-9 ._]+$", "", t).strip()

    # 2. Remove common morning/evening digest tags
    digest_patterns = [
        r":\s*Morning\s+Rundown.*$",
        r":\s*Morning\s+Briefing.*$",
        r":\s*Evening\s+Briefing.*$",
        r":\s*Daily\s+Digest.*$",
        r":\s*5\s+things\s+to\s+know.*$",
        r":\s*What\s+to\s+know.*$",
        r"^Morning\s+Rundown:\s*",
        r"^Morning\s+Briefing:\s*",
        r"^What\s+we['’]re\s+watching:\s*",
    ]
    for pat in digest_patterns:
        t = re.sub(pat, "", t, flags=re.IGNORECASE).strip()

    # 3. Detect and remove composite secondary entertainment/lifestyle appendages
    # e.g., "... and Taylor Swift sets VMAs record" or "... and Travis Kelce ..."
    composite_match = re.search(
        r"^(.*?)\s+and\s+(?:Taylor Swift|Beyonce|Kardashian|Travis Kelce|VMAs|Grammys|Oscars|Box Office|Celebrity|Hollywood|Horoscope|Weather).*$",
        t,
        flags=re.IGNORECASE,
    )
    if composite_match:
        t = composite_match.group(1).strip()

    # 4. Clean up trailing punctuation or conjunctions
    t = re.sub(r"\s+(?:and|or|plus|with)\s*$", "", t, flags=re.IGNORECASE).strip()
    return t


def extract_source_from_title(title: str, default_source: str) -> tuple[str, str]:
    """Many feeds append ' - SourceName' to the end of the title."""
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts[1].strip()) > 1:
            raw_title = parts[0].strip()
            return sanitize_news_headline(raw_title), parts[1].strip()
    return sanitize_news_headline(title.strip()), default_source


# 10-minute in-memory cache for RSS feeds
_FEED_CACHE: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


async def fetch_feed_entries(feed_info: Dict[str, str]) -> List[Dict[str, Any]]:
    """Asynchronously fetch and parse an RSS feed with a 10-minute in-memory cache."""
    url = feed_info["url"]
    default_source = feed_info.get("default_source", "News Feed")
    now = datetime.now(timezone.utc)

    # Check cache first
    if url in _FEED_CACHE:
        cached_time, cached_entries = _FEED_CACHE[url]
        if (now - cached_time).total_seconds() < CACHE_TTL_SECONDS:
            return cached_entries

    entries = []

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch feed {url}, status: {resp.status_code}")
                # Return stale cache if available
                if url in _FEED_CACHE:
                    return _FEED_CACHE[url][1]
                return []
            content = resp.text


        parsed = feedparser.parse(content)
        for entry in parsed.entries:
            # Extract raw date
            raw_date = entry.get("published_parsed") or entry.get("published") or entry.get("updated")
            pub_dt = parse_datetime(raw_date)

            raw_title = entry.get("title", "")
            clean_title, source = extract_source_from_title(raw_title, default_source)

            link = entry.get("link", "")
            raw_summary = entry.get("summary") or entry.get("description") or ""
            summary = clean_html(raw_summary)

            # Extract direct media / image attachments from RSS feed
            image_urls = []
            if "media_content" in entry and isinstance(entry["media_content"], list):
                for m in entry["media_content"]:
                    if isinstance(m, dict) and m.get("url"):
                        image_urls.append(m["url"])
            if "media_thumbnail" in entry and isinstance(entry["media_thumbnail"], list):
                for m in entry["media_thumbnail"]:
                    if isinstance(m, dict) and m.get("url"):
                        image_urls.append(m["url"])
            if "enclosures" in entry and isinstance(entry["enclosures"], list):
                for enc in entry["enclosures"]:
                    if isinstance(enc, dict) and enc.get("type", "").startswith("image") and enc.get("href"):
                        image_urls.append(enc["href"])
            if "<img" in raw_summary:
                try:
                    s_soup = BeautifulSoup(raw_summary, "html.parser")
                    for img in s_soup.find_all("img"):
                        src = img.get("src")
                        if src and src.startswith("http"):
                            image_urls.append(src)
                except Exception:
                    pass

            entries.append({
                "title": clean_title,
                "source": source,
                "url": link,
                "published_dt": pub_dt,
                "raw_date": entry.get("published") or entry.get("updated") or "",
                "raw_summary": summary,
                "image_urls": list(dict.fromkeys(image_urls)),
            })
    except Exception as e:
        logger.error(f"Error parsing feed {url}: {e}")

    if entries:
        _FEED_CACHE[url] = (now, entries)

    return entries


async def fetch_news_for_region(
    region: Region,
    max_age_hours: float = 24.0,
    max_candidates: int = 25,
) -> List[Dict[str, Any]]:
    """Fetch candidate news items for a given region strictly published within the last 24 hours."""
    feed_list = FEEDS_INDIA if region == Region.INDIA else FEEDS_WORLDWIDE
    now_utc = datetime.now(timezone.utc)

    all_entries: List[Dict[str, Any]] = []
    for f in feed_list:
        feed_entries = await fetch_feed_entries(f)
        all_entries.extend(feed_entries)

    # Filter within last 24 hours & deduplicate by title similarity
    valid_candidates = []
    seen_titles = set()

    for item in all_entries:
        pub_dt = item.get("published_dt")
        is_fresh, age_hours = is_within_last_24_hours(pub_dt, max_hours=max_age_hours, reference_time=now_utc)
        
        # If feed date was missing or within 24h
        if is_fresh and pub_dt is not None:
            # Simple title normalization for deduplication
            norm_title = re.sub(r"[^a-zA-Z0-9 ]", "", item["title"]).lower()[:60]
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)

            valid_candidates.append({
                "title": item["title"],
                "source": item["source"],
                "url": item["url"],
                "published_at": pub_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "published_timestamp": pub_dt.timestamp(),
                "age_hours": round(age_hours, 1),
                "summary": item["raw_summary"][:400] if item["raw_summary"] else item["title"],
                "region": region.value,
                "image_urls": item.get("image_urls", []),
            })

    # Sort primarily by recency (newest first)
    valid_candidates.sort(key=lambda x: x["published_timestamp"], reverse=True)
    return valid_candidates[:max_candidates]
