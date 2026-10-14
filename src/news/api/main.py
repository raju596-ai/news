import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ..config import settings
from ..agents.base import Region, AgentPhase, PipelineEvent
from ..agents.orchestrator import OrchestratorAgent
from ..agents.orchestrator.state import global_state, global_broadcaster
from ..models.article import TopNewsReport

app = FastAPI(
    title="AI News Video Generation Platform",
    description="Multi-Agent Autonomous Real-Time News Video Generation Platform",
    version="2.0.0",
)

# Enable CORS for external dashboards and microservices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
orchestrator = OrchestratorAgent()


# ==============================================================================
# UI & Static Serving
# ==============================================================================

@app.get("/", tags=["UI"])
async def serve_ui():
    """Serve the news video generator dashboard frontend."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "service": "AI News Video Generation Platform",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/style.css", include_in_schema=False)
async def serve_css():
    css_path = STATIC_DIR / "style.css"
    if css_path.exists():
        return FileResponse(str(css_path), media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/app.js", include_in_schema=False)
async def serve_js():
    js_path = STATIC_DIR / "app.js"
    if js_path.exists():
        return FileResponse(str(js_path), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


# Mount media files for direct thumbnail/slide access
if settings.MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")


# ==============================================================================
# Workflow Endpoints (SSE Stream, Start, Status)
# ==============================================================================

@app.post("/api/v1/workflow/start", tags=["Workflow"])
async def start_workflow(
    background_tasks: BackgroundTasks,
    auto_render: bool = Query(True, description="Render full MP4 video for all 10 stories"),
):
    """Trigger the multi-agent AI News Video Generation Workflow."""
    if global_state.is_running:
        return {
            "status": "already_running",
            "message": "Workflow is already active.",
            "overall_progress": global_state.overall_progress,
        }

    # Launch workflow in background task
    async def _run():
        await orchestrator.run_full_pipeline(auto_render_videos=auto_render)

    background_tasks.add_task(_run)

    return {
        "status": "started",
        "message": "Master Orchestrator initiated Global & India news video generation.",
        "auto_render": auto_render,
    }


@app.get("/api/v1/workflow/stream", tags=["Workflow"])
async def stream_workflow_events():
    """Server-Sent Events (SSE) stream broadcasting real-time progress for all agents and stories."""
    queue = global_broadcaster.subscribe()

    async def event_generator():
        try:
            # Emit current status as first packet
            init_event = {
                "stage": global_state.active_phase,
                "message": "Connected to NewsIntel Telemetry Stream",
                "progress": global_state.overall_progress,
                "is_running": global_state.is_running,
            }
            yield f"data: {json.dumps(init_event)}\n\n"

            while True:
                try:
                    event: PipelineEvent = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {json.dumps(event.model_dump())}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield f": heartbeat\n\n"
        except asyncio.CancelledError:
            global_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/workflow/status", tags=["Workflow"])
async def get_workflow_status():
    """Retrieve current pipeline state including Top 5 World and Top 5 India stories."""
    return {
        "is_running": global_state.is_running,
        "active_phase": global_state.active_phase,
        "overall_progress": global_state.overall_progress,
        "world_stories": [s.model_dump() for s in global_state.world_stories],
        "india_stories": [s.model_dump() for s in global_state.india_stories],
    }


@app.post("/api/v1/story/{story_id}/generate", tags=["Workflow"])
async def generate_single_story_video(story_id: str, background_tasks: BackgroundTasks):
    """Trigger on-demand video generation for a specific story."""
    story = global_state.story_map.get(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story ID not found.")

    async def _run_story():
        await orchestrator.process_story_full(story)

    background_tasks.add_task(_run_story)

    return {
        "status": "processing",
        "story_id": story_id,
        "title": story.title,
    }


# ==============================================================================
# Video Preview & Download Endpoints
# ==============================================================================

@app.get("/api/v1/videos/{story_id}/preview", tags=["Videos"])
async def preview_video(story_id: str):
    """Stream final rendered MP4 video for HTML5 preview playback."""
    story = global_state.story_map.get(story_id)
    video_path = None

    if story and story.media.video_path:
        p = Path(story.media.video_path)
        if p.exists():
            video_path = p

    # Fallback to checking media folder directly
    if not video_path:
        candidate = settings.MEDIA_DIR / story_id / "final_news_video.mp4"
        if candidate.exists():
            video_path = candidate

    if not video_path:
        raise HTTPException(status_code=404, detail="Video is still rendering or has not been generated.")

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"news_{story_id}.mp4",
    )


@app.get("/api/v1/videos/{story_id}/download", tags=["Videos"])
async def download_video(story_id: str):
    """Download final rendered MP4 video file."""
    story = global_state.story_map.get(story_id)
    video_path = None

    if story and story.media.video_path:
        p = Path(story.media.video_path)
        if p.exists():
            video_path = p

    if not video_path:
        candidate = settings.MEDIA_DIR / story_id / "final_news_video.mp4"
        if candidate.exists():
            video_path = candidate

    if not video_path:
        raise HTTPException(status_code=404, detail="Video file not found.")

    from ..tools.youtube_metadata import get_story_download_basename
    base_name = get_story_download_basename(story, story_id)
    filename = f"{base_name}.mp4"

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==============================================================================
# YouTube Upload Metadata Endpoints
# ==============================================================================

@app.get("/api/v1/story/{story_id}/youtube-details", tags=["YouTube"])
async def get_story_youtube_details(story_id: str):
    """Retrieve complete YouTube upload details (Title, Description, 20+ Tags, Category, etc.) for a specific story."""
    from ..tools.youtube_metadata import generate_youtube_metadata

    story = global_state.story_map.get(story_id)
    if not story:
        # Check if story folder exists on disk to reconstruct basic story
        story_folder = settings.MEDIA_DIR / story_id
        if story_folder.exists():
            from ..agents.base import NewsStory, Region
            story = NewsStory(
                id=story_id,
                region=Region.WORLDWIDE,
                rank=1,
                title="Global News Intelligence Update",
                summary="Verified 24-hour news intelligence broadcast.",
                url="https://news.google.com",
                source="NewsIntel Intelligence Feed",
                published_at=datetime.now(timezone.utc),
            )
        else:
            raise HTTPException(status_code=404, detail=f"Story {story_id} not found.")

    details = generate_youtube_metadata(story)
    return details


@app.get("/api/v1/story/{story_id}/metadata-file", tags=["YouTube"])
async def get_story_metadata_file(story_id: str):
    """Retrieve raw text content of the video upload metadata file in the required template format."""
    from ..tools.youtube_metadata import generate_youtube_metadata, save_metadata_file

    story = global_state.story_map.get(story_id)
    if not story:
        story_folder = settings.MEDIA_DIR / story_id
        if story_folder.exists():
            from ..agents.base import NewsStory, Region
            story = NewsStory(
                id=story_id,
                region=Region.WORLDWIDE,
                rank=1,
                title="Global News Intelligence Update",
                summary="Verified 24-hour news intelligence broadcast.",
                url="https://news.google.com",
                source="NewsIntel Intelligence Feed",
                published_at=datetime.now(timezone.utc),
            )
        else:
            raise HTTPException(status_code=404, detail=f"Story {story_id} not found.")

    meta_file = settings.MEDIA_DIR / story_id / "metadata.txt"
    if meta_file.exists():
        content = meta_file.read_text(encoding="utf-8")
    else:
        details = generate_youtube_metadata(story)
        content = details.get("metadata_file", "")
        save_metadata_file(story)

    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@app.get("/api/v1/story/{story_id}/metadata-file/download", tags=["YouTube"])
async def download_story_metadata_file(story_id: str):
    """Download the metadata.txt upload file for a specific story video."""
    from ..tools.youtube_metadata import generate_youtube_metadata, save_metadata_file

    story = global_state.story_map.get(story_id)
    if not story:
        story_folder = settings.MEDIA_DIR / story_id
        if story_folder.exists():
            from ..agents.base import NewsStory, Region
            story = NewsStory(
                id=story_id,
                region=Region.WORLDWIDE,
                rank=1,
                title="Global News Intelligence Update",
                summary="Verified 24-hour news intelligence broadcast.",
                url="https://news.google.com",
                source="NewsIntel Intelligence Feed",
                published_at=datetime.now(timezone.utc),
            )
        else:
            raise HTTPException(status_code=404, detail=f"Story {story_id} not found.")

    meta_file = settings.MEDIA_DIR / story_id / "metadata.txt"
    if not meta_file.exists():
        meta_file = save_metadata_file(story)

    from ..tools.youtube_metadata import get_story_download_basename
    base_name = get_story_download_basename(story, story_id)
    filename = f"{base_name}.txt"

    return FileResponse(
        str(meta_file),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/youtube/auth-status", tags=["YouTube"])
async def get_youtube_auth_status():
    """Check whether YouTube client_secret.json and token.json are configured."""
    from ..tools.youtube_uploader import check_youtube_auth_status
    return check_youtube_auth_status()


@app.get("/api/v1/story/{story_id}/upload-progress", tags=["YouTube"])
async def get_story_upload_progress(story_id: str):
    """Retrieve real-time YouTube upload progress percentage and status."""
    from ..tools.youtube_uploader import get_upload_progress
    return get_upload_progress(story_id)


@app.post("/api/v1/story/{story_id}/upload-youtube", tags=["YouTube"])
async def upload_story_to_youtube(story_id: str, rank: Optional[int] = Query(None)):
    """Upload rendered news video and metadata directly to YouTube with automated publication schedule."""
    from ..tools.youtube_uploader import upload_video_to_youtube

    story = global_state.story_map.get(story_id)
    story_dir = settings.MEDIA_DIR / story_id

    # Determine rank (1 for 1st video, 2 for 2nd video)
    story_rank = 1
    if rank is not None:
        story_rank = rank
    elif story:
        story_rank = getattr(story, "rank", 1)
    else:
        for idx, s in enumerate(global_state.world_stories):
            if s.id == story_id:
                story_rank = getattr(s, "rank", idx + 1)
                break
        for idx, s in enumerate(global_state.india_stories):
            if s.id == story_id:
                story_rank = getattr(s, "rank", idx + 1)
                break

    # Check for video file
    video_path = None
    if story and story.media.video_path and Path(story.media.video_path).exists():
        video_path = Path(story.media.video_path)
    elif (story_dir / "final_news_video.mp4").exists():
        video_path = story_dir / "final_news_video.mp4"

    if not video_path:
        raise HTTPException(status_code=400, detail="Video has not been generated or rendered yet.")

    metadata_path = story_dir / "metadata.txt"
    if not metadata_path.exists():
        from ..tools.youtube_metadata import save_metadata_file
        if story:
            save_metadata_file(story, story_dir)

    try:
        result = await asyncio.to_thread(
            upload_video_to_youtube,
            video_path=video_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
            story_id=story_id,
            rank=story_rank,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {str(e)}")


# ==============================================================================
# Meta (Facebook & Instagram) Endpoints
# ==============================================================================

@app.get("/api/v1/meta/auth-status", tags=["Meta"])
async def get_meta_auth_status():
    """Check if Facebook and Instagram credentials are configured."""
    from ..tools.meta_uploader import load_meta_credentials
    fb_creds, ig_creds = load_meta_credentials()
    return {
        "facebook_configured": bool(fb_creds.get("page_id") and fb_creds.get("access_token")),
        "instagram_configured": bool(ig_creds.get("account_id") and ig_creds.get("access_token")),
        "facebook_page_id": fb_creds.get("page_id", ""),
        "instagram_account_id": ig_creds.get("account_id", ""),
    }


@app.get("/api/v1/story/{story_id}/upload-facebook/status", tags=["Meta"])
async def get_story_facebook_progress(story_id: str):
    """Retrieve real-time Facebook upload progress percentage and status."""
    from ..tools.meta_uploader import get_facebook_upload_progress
    return get_facebook_upload_progress(story_id)


@app.post("/api/v1/story/{story_id}/upload-facebook", tags=["Meta"])
async def upload_story_to_facebook(story_id: str):
    """Upload rendered news video directly to Facebook Page."""
    from ..tools.meta_uploader import upload_video_to_facebook

    story = global_state.story_map.get(story_id)
    story_dir = settings.MEDIA_DIR / story_id

    video_path = None
    if story and story.media.video_path and Path(story.media.video_path).exists():
        video_path = Path(story.media.video_path)
    elif (story_dir / "final_news_video.mp4").exists():
        video_path = story_dir / "final_news_video.mp4"

    if not video_path:
        raise HTTPException(status_code=400, detail="Video has not been generated or rendered yet.")

    metadata_path = story_dir / "metadata.txt"
    if not metadata_path.exists():
        from ..tools.youtube_metadata import save_metadata_file
        if story:
            save_metadata_file(story, story_dir)

    try:
        result = await asyncio.to_thread(
            upload_video_to_facebook,
            video_path=video_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
            story_id=story_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Facebook upload failed: {str(e)}")


@app.get("/api/v1/story/{story_id}/upload-instagram/status", tags=["Meta"])
async def get_story_instagram_progress(story_id: str):
    """Retrieve real-time Instagram upload progress percentage and status."""
    from ..tools.meta_uploader import get_instagram_upload_progress
    return get_instagram_upload_progress(story_id)


@app.post("/api/v1/story/{story_id}/upload-instagram", tags=["Meta"])
async def upload_story_to_instagram(story_id: str):
    """Upload rendered news video directly to Instagram account."""
    from ..tools.meta_uploader import upload_video_to_instagram

    story = global_state.story_map.get(story_id)
    story_dir = settings.MEDIA_DIR / story_id

    video_path = None
    if story and story.media.video_path and Path(story.media.video_path).exists():
        video_path = Path(story.media.video_path)
    elif (story_dir / "final_news_video.mp4").exists():
        video_path = story_dir / "final_news_video.mp4"

    if not video_path:
        raise HTTPException(status_code=400, detail="Video has not been generated or rendered yet.")

    metadata_path = story_dir / "metadata.txt"
    if not metadata_path.exists():
        from ..tools.youtube_metadata import save_metadata_file
        if story:
            save_metadata_file(story, story_dir)

    try:
        result = await asyncio.to_thread(
            upload_video_to_instagram,
            video_path=video_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
            story_id=story_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Instagram upload failed: {str(e)}")



# ==============================================================================
# Slides Inspection Endpoint
# ==============================================================================

@app.get("/api/v1/story/{story_id}/slides", tags=["Workflow"])
async def get_story_slides(story_id: str):
    """Retrieve detailed slide breakdown for inspection (slides, beats, narrations, image URLs)."""
    story = global_state.story_map.get(story_id)
    story_dir = settings.MEDIA_DIR / story_id
    images_dir = story_dir / "images"

    slides_data = []

    if story and story.script and story.script.segments:
        for idx, seg in enumerate(story.script.segments):
            slide_file = images_dir / f"slide_{idx}_{seg.beat.lower().replace(' ', '_')}.jpg"
            img_url = f"/media/{story_id}/images/{slide_file.name}" if slide_file.exists() else None
            slides_data.append({
                "slide_index": idx + 1,
                "beat": seg.beat,
                "narration": seg.narration,
                "image_url": img_url,
                "exists": slide_file.exists(),
            })
    elif images_dir.exists():
        found_slides = sorted(list(images_dir.glob("slide_*.jpg")))
        for idx, sf in enumerate(found_slides):
            slides_data.append({
                "slide_index": idx + 1,
                "beat": sf.stem.replace("slide_", "").replace("_", " ").title(),
                "narration": story.summary if story else "News broadcast slide",
                "image_url": f"/media/{story_id}/images/{sf.name}",
                "exists": True,
            })

    return {
        "story_id": story_id,
        "title": story.title if story else story_id,
        "total_slides": len(slides_data),
        "slides": slides_data,
    }


@app.post("/api/v1/workflow/real-generation", tags=["Workflow"])
async def start_real_generation_workflow(
    background_tasks: BackgroundTasks,
    auto_render: bool = Query(True, description="Render full MP4 video for all stories using NVIDIA AI imagery"),
):
    """Trigger the dedicated Real Broadcast Generation Workflow with NVIDIA FLUX image generation and Llama Vision verification."""
    if global_state.is_running:
        return {
            "status": "already_running",
            "message": "Workflow is already active.",
            "overall_progress": global_state.overall_progress,
        }

    async def _run():
        await orchestrator.run_full_pipeline(auto_render_videos=auto_render)

    background_tasks.add_task(_run)

    return {
        "status": "started",
        "workflow": "real_broadcast_generation",
        "message": "Real Broadcast Generation initiated with NVIDIA FLUX.2-klein-4b & Llama 3.2 Vision verification.",
        "auto_render": auto_render,
        "nvidia_configured": bool(settings.NVIDIA_API_KEY),
    }


# ==============================================================================
# Dynamic Configuration & Model Presets
# ==============================================================================

class ConfigUpdateRequest(BaseModel):
    model_name: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    aspect_ratio: Optional[str] = None


class SlideRegenRequest(BaseModel):
    custom_prompt: Optional[str] = None
    model_name: Optional[str] = None


@app.get("/api/v1/config/options", tags=["Configuration"])
async def get_config_options():
    """Retrieve available NVIDIA models, regional languages, and video aspect ratios."""
    return {
        "models": [
            {"id": settings.NVIDIA_IMAGE_MODEL_TURBO, "name": "FLUX.1-schnell (Turbo 1.5s)", "badge": "TURBO"},
            {"id": settings.NVIDIA_IMAGE_MODEL_BALANCED, "name": "FLUX.2-klein-4b (Balanced 3.5s)", "badge": "BALANCED"},
            {"id": settings.NVIDIA_IMAGE_MODEL_PRO, "name": "FLUX.1-dev (Pro Editorial 7s)", "badge": "PRO"},
        ],
        "current_model": settings.NVIDIA_IMAGE_MODEL,
        "active_model": settings.NVIDIA_IMAGE_MODEL,
        "languages": [
            {"code": "en", "name": "English", "flag": "🌐"},
            {"code": "te", "name": "Telugu (తెలుగు)", "flag": "🇮🇳"},
            {"code": "hi", "name": "Hindi (हिन्दी)", "flag": "🇮🇳"},
        ],
        "current_language": settings.DEFAULT_LANGUAGE,
        "active_language": settings.DEFAULT_LANGUAGE,
        "aspect_ratios": [
            {"id": "16:9", "name": "16:9 Landscape (YouTube)"},
            {"id": "9:16", "name": "9:16 Vertical (Shorts / Reels)"},
            {"id": "both", "name": "Dual Format (16:9 + 9:16)"},
        ],
        "current_format": "16:9",
        "active_aspect_ratio": "16:9",
    }


@app.post("/api/v1/config/set", tags=["Configuration"])
async def update_config(
    body: Optional[ConfigUpdateRequest] = None,
    model: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    aspect_ratio: Optional[str] = Query(None),
):
    """Update active image model or default language on the fly via JSON body or query params."""
    eff_model = (body.model_name or body.model) if body else model
    eff_lang = body.language if body else language
    eff_aspect = body.aspect_ratio if body else aspect_ratio

    if eff_model:
        settings.NVIDIA_IMAGE_MODEL = eff_model
    if eff_lang:
        settings.DEFAULT_LANGUAGE = eff_lang
    return {
        "status": "updated",
        "current_model": settings.NVIDIA_IMAGE_MODEL,
        "active_model": settings.NVIDIA_IMAGE_MODEL,
        "current_language": settings.DEFAULT_LANGUAGE,
        "active_language": settings.DEFAULT_LANGUAGE,
        "current_format": eff_aspect or "16:9",
        "aspect_ratio": eff_aspect or "16:9",
    }


# ==============================================================================
# Slide Re-Roll & Inspection Endpoints
# ==============================================================================

@app.post("/api/v1/story/{story_id}/slide/{slide_idx}/regenerate", tags=["Workflow"])
async def regenerate_story_slide(
    story_id: str,
    slide_idx: int,
    body: Optional[SlideRegenRequest] = None,
    custom_prompt: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
):
    """Regenerate a specific slide visual in real time with NVIDIA FLUX and Vision verification."""
    story = global_state.story_map.get(story_id)
    if not story:
        # Reconstruct basic story from media dir if not in memory
        story_folder = settings.MEDIA_DIR / story_id
        if story_folder.exists():
            from ..agents.base import NewsStory, Region
            story = NewsStory(
                id=story_id,
                region=Region.INDIA,
                rank=1,
                title="Broadcast News Story",
                summary="Verified 24-hour news intelligence broadcast.",
                url="https://news.google.com",
                source="NewsIntel Feed",
                published_at=datetime.now(timezone.utc),
            )
        else:
            raise HTTPException(status_code=404, detail="Story not found")

    eff_prompt = (body.custom_prompt if body and body.custom_prompt else custom_prompt)
    eff_model = (body.model_name if body and body.model_name else model_name)

    from ..agents.image_agent.agent import ImageResearchAgent
    img_agent = ImageResearchAgent()
    target_model = eff_model or settings.NVIDIA_IMAGE_MODEL

    new_path = await img_agent.regenerate_single_slide(
        story=story,
        slide_index=slide_idx,
        custom_prompt=eff_prompt,
        model_name=target_model,
    )
    if not new_path:
        raise HTTPException(status_code=500, detail="Slide re-roll failed.")

    p = Path(new_path)
    return {
        "status": "success",
        "story_id": story_id,
        "slide_index": slide_idx,
        "image_url": f"/media/{story_id}/images/{p.name}?t={int(datetime.now().timestamp())}",
        "image_path": str(p),
        "model": target_model,
        "file_name": p.name,
    }


# ==============================================================================
# A/B Thumbnails & Community Content Endpoints
# ==============================================================================

@app.get("/api/v1/story/{story_id}/thumbnails", tags=["YouTube"])
async def get_story_thumbnails(story_id: str):
    """Retrieve Option A and Option B thumbnails for A/B testing."""
    story_dir = settings.MEDIA_DIR / story_id
    thumb_a = story_dir / "thumbnail.jpg"
    thumb_b = story_dir / "thumbnail_b.jpg"

    return {
        "story_id": story_id,
        "thumbnail_a": f"/media/{story_id}/thumbnail.jpg" if thumb_a.exists() else None,
        "thumbnail_a_url": f"/media/{story_id}/thumbnail.jpg" if thumb_a.exists() else None,
        "thumbnail_b": f"/media/{story_id}/thumbnail_b.jpg" if thumb_b.exists() else None,
        "thumbnail_b_url": f"/media/{story_id}/thumbnail_b.jpg" if thumb_b.exists() else None,
    }


@app.get("/api/v1/story/{story_id}/community-post", tags=["YouTube"])
async def get_story_community_post(story_id: str):
    """Retrieve auto-generated YouTube Community Post and Pinned Comment."""
    story_dir = settings.MEDIA_DIR / story_id
    comm_file = story_dir / "community_post.txt"
    pinned_file = story_dir / "pinned_comment.txt"

    comm_text = comm_file.read_text(encoding="utf-8") if comm_file.exists() else ""
    pinned_text = pinned_file.read_text(encoding="utf-8") if pinned_file.exists() else ""

    return {
        "story_id": story_id,
        "community_post": comm_text,
        "pinned_comment": pinned_text,
    }


# ==============================================================================
# 9:16 Vertical Video Endpoints (Shorts / Reels)
# ==============================================================================

@app.post("/api/v1/story/{story_id}/generate-vertical", tags=["Videos"])
async def generate_vertical_video_endpoint(story_id: str, background_tasks: BackgroundTasks):
    """Trigger rendering of 9:16 vertical video for YouTube Shorts and Instagram Reels."""
    story = global_state.story_map.get(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    async def _render_vert():
        from ..agents.video_assembler.agent import VideoAssemblyAgent
        assembler = VideoAssemblyAgent()
        await assembler.render_vertical_video(story)

    background_tasks.add_task(_render_vert)
    return {
        "status": "rendering",
        "story_id": story_id,
        "format": "9:16 Vertical (Shorts/Reels)",
    }


@app.get("/api/v1/videos/{story_id}/preview-vertical", tags=["Videos"])
async def preview_vertical_video(story_id: str):
    """Stream rendered 9:16 vertical video."""
    story_dir = settings.MEDIA_DIR / story_id
    v_path = story_dir / "final_news_video_vertical.mp4"
    if not v_path.exists():
        raise HTTPException(status_code=404, detail="Vertical video not yet rendered.")

    return FileResponse(str(v_path), media_type="video/mp4", filename=f"news_vertical_{story_id}.mp4")


@app.get("/api/v1/videos/{story_id}/download-vertical", tags=["Videos"])
async def download_vertical_video(story_id: str):
    """Download 9:16 vertical MP4 video file."""
    story_dir = settings.MEDIA_DIR / story_id
    v_path = story_dir / "final_news_video_vertical.mp4"
    if not v_path.exists():
        raise HTTPException(status_code=404, detail="Vertical video not found.")

    from ..tools.youtube_metadata import get_story_download_basename
    story = global_state.story_map.get(story_id)
    base_name = get_story_download_basename(story, story_id)
    return FileResponse(
        str(v_path),
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{base_name}_shorts_9x16.mp4"'},
    )


# ==============================================================================
# Health & Info Endpoints
# ==============================================================================

@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nvidia_configured": bool(settings.NVIDIA_API_KEY),
        "nvidia_image_model": settings.NVIDIA_IMAGE_MODEL,
        "nvidia_vision_model": settings.NVIDIA_VISION_MODEL,
        "default_language": settings.DEFAULT_LANGUAGE,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY),
        "ffmpeg_available": bool(settings.FFMPEG_PATH and Path(settings.FFMPEG_PATH).exists()),
        "ffmpeg_path": settings.FFMPEG_PATH,
        "is_pipeline_running": global_state.is_running,
    }
