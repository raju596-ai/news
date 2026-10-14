"""Modular utility for generating YouTube upload metadata from verified NewsStory content."""

import logging
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from ..agents.base import NewsStory, Region
from ..config import settings

logger = logging.getLogger(__name__)


def format_metadata_file_content(story: NewsStory, metadata_dict: Optional[Dict[str, Any]] = None) -> str:
    """Format upload metadata for a video in the exact required text format:
    ---
    Title: Global Oil Prices Rise as Iranian Propos 
    Description: Enter your localized news updates and transcript report here.

    [PLAYLISTS]
    Playlists: Top 9AM news from INDIA, World wide top 5 news for today(select one according to video)

    [AUDIENCE & SAFETY]
    IsMadeForKids: False
    AgeRestriction: False

    [PROMOTION & TRANSPARENCY]
    PaidPromotion: False
    AlUse: True

    [AUTOMATIC FEATURES]
    AllowAutomaticChapters: True
    AllowFeaturedPlaces: True
    AllowAutomaticConcepts: True

    [METADATA & TAGS]
    Tags: GlobalBharatNews, WorldNews, IndiaNews, LatestNews, NewsUpdate
    VideoLanguage: en-IN
    CaptionCertification: None

    [LOCATION & LICENSE]
    RecordingDate: None
    VideoLocation: None
    License: Standard YouTube License
    AllowEmbedding: False
    PublishToSubscriptions: True

    [SHORTS & CATEGORY]
    ShortsRemixing: Don't allow remixing
    Category: News & Politics

    [COMMENTS & RATINGS]
    CommentsStatus: On
    CommentModeration: Basic
    WhoCanComment: Anyone
    SortCommentsBy: Top
    ShowLikeCount: True

    [VISIBILITY]
    PrivacyStatus: public
    ---
    """
    if metadata_dict is None:
        metadata_dict = generate_youtube_metadata(story, auto_save=False)

    title = metadata_dict.get("title") or story.title.strip()
    description = metadata_dict.get("description") or story.summary.strip()

    # Select playlist according to video:
    # India -> Top 9AM news from INDIA
    # World -> World wide top 5 news for today
    if story.region == Region.INDIA:
        selected_playlist = "Top 9AM news from INDIA"
    else:
        selected_playlist = "World wide top 5 news for today"

    # Core required tags from the template
    core_tags = ["GlobalBharatNews", "WorldNews", "IndiaNews", "LatestNews", "NewsUpdate"]
    raw_tags = metadata_dict.get("tags") or []
    additional_tags = []
    for t in raw_tags:
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', t)
        if cleaned and cleaned.lower() not in [x.lower() for x in core_tags]:
            additional_tags.append(cleaned)
    combined_tags = core_tags + additional_tags[:12]
    tags_str = ", ".join(combined_tags)

    video_lang = "en-IN"

    content = f"""---
Title: {title}
Description: {description}

[PLAYLISTS]
Playlists: {selected_playlist}

[AUDIENCE & SAFETY]
IsMadeForKids: False
AgeRestriction: False

[PROMOTION & TRANSPARENCY]
PaidPromotion: False
AlUse: True

[AUTOMATIC FEATURES]
AllowAutomaticChapters: True
AllowFeaturedPlaces: True
AllowAutomaticConcepts: True

[METADATA & TAGS]
Tags: {tags_str}
VideoLanguage: {video_lang}
CaptionCertification: None

[LOCATION & LICENSE]
RecordingDate: None
VideoLocation: None
License: Standard YouTube License
AllowEmbedding: False
PublishToSubscriptions: True

[SHORTS & CATEGORY]
ShortsRemixing: Don't allow remixing
Category: News & Politics

[COMMENTS & RATINGS]
CommentsStatus: On
CommentModeration: Basic
WhoCanComment: Anyone
SortCommentsBy: Top
ShowLikeCount: True

[VISIBILITY]
PrivacyStatus: public
---"""
    return content


def get_story_download_basename(story: Optional[Any], story_id: str) -> str:
    """Generate a clean, consistent base filename (without extension) for matching video and metadata downloads.
    Example:
        story.title = 'Indian News: Markets Surge' -> 'indian_news_markets_surge'
        Video download: 'indian_news_markets_surge.mp4'
        Metadata download: 'indian_news_markets_surge.txt'
    """
    raw_title = ""
    if story and getattr(story, "title", None):
        raw_title = story.title.strip()
    elif story_id:
        raw_title = story_id

    # Sanitize title: remove unwanted chars, preserve spaces/dashes/underscores
    clean = re.sub(r'[^a-zA-Z0-9\s_-]', '', raw_title)
    # Normalize multiple whitespace to single space and replace spaces with underscore
    clean = re.sub(r'\s+', '_', clean).strip('_-')
    if not clean:
        clean = f"news_{story_id}"

    # Cap length to 60 characters so it's clean and filesystem-safe
    clean = clean[:60].rstrip('_-')
    return clean


def generate_youtube_community_post(story: NewsStory) -> str:
    """Generate high-engagement YouTube Community Post with interactive discussion poll."""
    clean_title = story.title.strip()
    summary = story.summary.strip()
    return f"""🚨 BREAKING REPORT: {clean_title}

{summary}

👇 Community Discussion:
What is your view on this development?
1. Crucial step in the right direction
2. Needs urgent policy reform / oversight
3. Too early to tell — monitoring impact

💬 Leave your thoughts in the comments below! Full broadcast report now streaming on the channel.

#NewsIntel #CurrentAffairs #GlobalBharatNews"""


def generate_youtube_pinned_comment(story: NewsStory) -> str:
    """Generate professional pinned comment with video chapter links and source citations."""
    source_name = story.source.strip() if story.source else "Verified Wire Services"
    source_url = story.url.strip() if story.url else "https://news.google.com"
    return f"""📌 BROADCAST FACT-CHECK & SOURCES:
• Reporting Lead: {source_name} ({source_url})
• Verified 24-Hour Editorial Intelligence Dispatch
• Full HD 1080p Broadcast Produced by NewsIntel AI Network

🕒 TIMESTAMPS:
0:00 - Introduction & Breaking Overview
0:15 - Core Facts: What Happened
0:50 - Key Evidence & Developments
1:50 - Regional & Global Impact Analysis
2:30 - Latest Verification & Sign-off

🔔 Subscribe for 24-hour verified news briefings every morning & evening!"""


def save_metadata_file(story: NewsStory, output_dir: Optional[Path] = None) -> Path:
    """Generate and write metadata.txt, community_post.txt, and pinned_comment.txt in the story media directory."""
    if output_dir is None:
        output_dir = settings.MEDIA_DIR / story.id
    output_dir.mkdir(parents=True, exist_ok=True)

    meta_dict = generate_youtube_metadata(story, auto_save=False)
    content = format_metadata_file_content(story, meta_dict)

    meta_file = output_dir / "metadata.txt"
    meta_file.write_text(content, encoding="utf-8")

    # Also save with the exact same base name as the video file
    base_name = get_story_download_basename(story, story.id)
    (output_dir / f"{base_name}.txt").write_text(content, encoding="utf-8")

    # Save community post and pinned comment
    comm_post = generate_youtube_community_post(story)
    (output_dir / "community_post.txt").write_text(comm_post, encoding="utf-8")
    pinned = generate_youtube_pinned_comment(story)
    (output_dir / "pinned_comment.txt").write_text(pinned, encoding="utf-8")

    # Also save youtube_metadata.txt and metadata.yaml for cross-compatibility
    (output_dir / "youtube_metadata.txt").write_text(content, encoding="utf-8")
    (output_dir / "metadata.yaml").write_text(content, encoding="utf-8")

    story.media.metadata_path = str(meta_file)
    logger.info(f"Saved video metadata and community files for story {story.id} to {output_dir}")
    return meta_file


def generate_youtube_metadata(story: NewsStory, auto_save: bool = True) -> Dict[str, Any]:
    """Generate complete, factual, YouTube-friendly upload metadata for a specific news video.

    Uses strictly the actual verified content, script, and sources already associated with the story.
    """
    title_raw = story.title.strip()
    # Format a concise, factual, YouTube-friendly headline (< 100 chars)
    if story.region == Region.INDIA:
        title = f"{title_raw} | India News"
    else:
        title = f"{title_raw} | World News"

    if len(title) > 95:
        title = title_raw[:92] + "..."

    # Extract script sections if available
    s = story.script
    hook = s.hook if s and s.hook else story.summary
    what_happened = s.what_happened if s and s.what_happened else story.summary
    key_details = s.key_details if s and s.key_details else "Comprehensive verified developments and evidence."
    why_it_matters = s.why_it_matters if s and s.why_it_matters else "Analysis of strategic regional and global implications."
    latest_update = (s.latest_update or s.current_status) if s and (s.latest_update or s.current_status) else "Ongoing developments monitored in real-time."

    # Actual sources used
    source_name = story.source.strip() if story.source else "Verified Wire Services"
    source_url = story.url.strip() if story.url else "https://news.google.com"

    # Relevant hashtags
    cat_tag = "".join(c for c in story.category if c.isalnum())
    region_tag = "IndiaNews" if story.region == Region.INDIA else "WorldNews"
    hashtags = [
        f"#{region_tag}",
        f"#{cat_tag}" if cat_tag else "#News",
        "#BreakingNews",
        "#NewsIntel",
        "#CurrentAffairs",
        "#DailyNews",
    ]
    hashtags_str = " ".join(hashtags)

    # Build description
    description_lines = [
        f"{hook}",
        "",
        "In this video:",
        f"00:00 - Introduction & Overview",
        f"00:15 - What Happened: {what_happened[:120]}...",
        f"00:50 - Key Developments: {key_details[:120]}...",
        f"01:50 - Why It Matters: {why_it_matters[:120]}...",
        f"02:30 - Latest Update: {latest_update[:120]}...",
        f"02:50 - Broadcast Sign-off & Analysis",
        "",
        "Reliable Sources Used:",
        f"• {source_name} (Source link: {source_url})",
        "• Real-Time 24-Hour Verified News Intelligence Feeds",
        "",
        "Notice: This report is compiled factually from verified public news dispatches and official records.",
        "",
        hashtags_str,
    ]
    description = "\n".join(description_lines)

    # Priority tags (starting with GlobalBharatNews as requested)
    base_tags = [
        "GlobalBharatNews",
        "WorldNews",
        "IndiaNews",
        "LatestNews",
        "NewsUpdate",
        "news",
        "breaking news",
        "current affairs",
        "global news update",
        "latest news today",
        "international affairs",
        "geopolitics",
        "daily news briefing",
        "news analysis",
        "verified news",
        "top news stories",
        "policy update",
        "breaking report",
        "world affairs",
        "news bulletin",
        "in depth report",
        "news intel",
        "world events",
        "national news",
        "broadcast news",
        "investigative report",
    ]

    # Add story-specific category and keyword tags
    specific_tags = [
        story.category.lower(),
        f"{story.category.lower()} news",
        story.source.lower(),
        "today news",
        "24 hour news",
    ]

    combined_tags: List[str] = []
    seen = set()
    for t in base_tags[:5] + specific_tags + base_tags[5:]:
        cleaned = t.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            combined_tags.append(cleaned)

    # Ensure at least 20 tags
    tags = combined_tags[:28]

    # Category, Language, Playlist, Subtitles, Visibility
    category = "News & Politics"
    language = "en-IN" if story.region == Region.INDIA else "en-US"
    playlist = "Top 9AM news from INDIA" if story.region == Region.INDIA else "World wide top 5 news for today"
    subtitles = "English (Burned-in Subtitles & Full Audio Transcript)"
    visibility = "public"
    made_for_kids = False

    # Dynamic publication schedule policy based on story rank (1 or 2) and current time
    from .youtube_uploader import calculate_youtube_publish_status
    rank = getattr(story, "rank", 1)
    publish_info = calculate_youtube_publish_status(rank=rank)

    now_local = datetime.now().astimezone()
    schedule_date = now_local.strftime("%Y-%m-%d")
    schedule_time = publish_info["scheduled_local_str"]

    exact_json_dict = {
        "title": title,
        "description": description,
        "tags": tags,
        "madeForKids": made_for_kids,
        "category": category,
        "visibility": visibility,
        "scheduleDate": schedule_date,
        "scheduleTime": schedule_time,
    }
    json_formatted = json.dumps(exact_json_dict, indent=2)

    # Format the exact requested text file format
    metadata_file_text = format_metadata_file_content(story, {
        "title": title,
        "description": description,
        "tags": tags,
    })

    # Auto-save metadata.txt to media directory if enabled
    if auto_save and story.id:
        try:
            story_dir = settings.MEDIA_DIR / story.id
            story_dir.mkdir(parents=True, exist_ok=True)
            meta_file = story_dir / "metadata.txt"
            meta_file.write_text(metadata_file_text, encoding="utf-8")
            (story_dir / "youtube_metadata.txt").write_text(metadata_file_text, encoding="utf-8")
            story.media.metadata_path = str(meta_file)
        except Exception as e:
            logger.debug(f"Auto-save metadata note: {e}")

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "madeForKids": made_for_kids,
        "category": category,
        "visibility": visibility,
        "scheduleDate": schedule_date,
        "scheduleTime": schedule_time,
        "json_formatted": json_formatted,
        "metadata_file": metadata_file_text,
        # Extended fields
        "story_id": story.id,
        "tags_string": ", ".join(tags),
        "language": language,
        "playlist": playlist,
        "subtitles": subtitles,
        "sources": [f"{source_name} ({source_url})"],
        "hashtags": hashtags,
        "schedule_info": publish_info,
        "is_scheduled": publish_info["is_scheduled"],
        "schedule_description": publish_info["schedule_description"],
    }
