import logging
import io
from pathlib import Path
from typing import Optional, List, Dict
import httpx
from PIL import Image, ImageDraw, ImageFont
from ...config import settings

logger = logging.getLogger(__name__)

# Curated high-resolution royalty-free editorial news imagery by beat & category
TOPIC_IMAGE_POOLS: Dict[str, List[str]] = {
    "breaking": [
        "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1920&q=85",  # Newsroom
        "https://images.unsplash.com/photo-1495020689067-958852a7765e?w=1920&q=85",  # Breaking news press
        "https://images.unsplash.com/photo-1526470608268-f674ce90ebd4?w=1920&q=85",  # Live broadcast camera
        "https://images.unsplash.com/photo-1572949645841-094f3a9c4c94?w=1920&q=85",  # Media coverage
    ],
    "geopolitics": [
        "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1920&q=85",  # International summit / flags
        "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=1920&q=85",  # Government hall
        "https://images.unsplash.com/photo-1517048676732-d65bc937f952?w=1920&q=85",  # Diplomatic conference
        "https://images.unsplash.com/photo-1568992687947-868a62a9f521?w=1920&q=85",  # Global assembly
    ],
    "tech": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1920&q=85",  # Microchip / AI
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1920&q=85",  # Digital Earth / Datacenter
        "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=1920&q=85",  # Tech workspace
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1920&q=85",  # Cybersecurity server
    ],
    "economy": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1920&q=85",  # Financial market charts
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=1920&q=85",  # Trading terminal
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=1920&q=85",  # Global business
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1920&q=85",  # Financial skyscrapers
    ],
    "science": [
        "https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=1920&q=85",  # Science research
        "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1920&q=85",  # Earth from orbit
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1920&q=85",  # Space deep field
        "https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=1920&q=85",  # Scientific laboratory
    ],
    "india": [
        "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=1920&q=85",  # India landmark / monument
        "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?w=1920&q=85",  # Delhi skyline / urban
        "https://images.unsplash.com/photo-1587474260584-136574528ed5?w=1920&q=85",  # New Delhi architecture
        "https://images.unsplash.com/photo-1506461883276-594a12b11cf3?w=1920&q=85",  # Parliament & government
    ],
    "general": [
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1920&q=85",  # Journalistic camera
        "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?w=1920&q=85",  # Broadcast news studio
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=1920&q=85",  # Global business
        "https://images.unsplash.com/photo-1495020689067-958852a7765e?w=1920&q=85",  # Newspaper press
    ]
}


def get_unique_topic_fallback(story_id: str, category: str = "general", index: int = 0) -> str:
    """Ensure that even in fallback cases, different stories receive different images using hash offset."""
    cat_key = (category or "general").lower()
    pool = TOPIC_IMAGE_POOLS.get("general", [])
    for k in TOPIC_IMAGE_POOLS:
        if k in cat_key:
            pool = TOPIC_IMAGE_POOLS[k]
            break

    # Seed offset using story_id hash to prevent identical selection across videos
    seed = sum(ord(c) for c in story_id) if story_id else 0
    pick_idx = (seed + index) % len(pool)
    return pool[pick_idx]


class ImageVerifierAndRenderer:
    """Verifies image relevance and renders YouTube Standard Full HD (1920x1080) broadcast graphic slides."""

    def __init__(self, target_width: int = 1920, target_height: int = 1080):
        self.width = target_width
        self.height = target_height

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        try:
            for font_name in ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf"]:
                try:
                    return ImageFont.truetype(font_name, size)
                except Exception:
                    pass
        except Exception:
            pass
        return ImageFont.load_default()

    async def fetch_web_image(self, url: str) -> Optional[Image.Image]:
        """Attempt to fetch an image from the web and validate format."""
        if not url or not url.startswith("http"):
            return None
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and ("image" in resp.headers.get("content-type", "") or len(resp.content) > 10000):
                    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    if img.width >= 400 and img.height >= 250:
                        return img
        except Exception as e:
            logger.debug(f"Failed to fetch image from {url}: {e}")
        return None

    def resize_and_crop(self, img: Image.Image) -> Image.Image:
        """Crop and resize image to exact 16:9 target dimensions (1920x1080)."""
        target_ratio = self.width / self.height
        img_ratio = img.width / img.height

        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))

        return img.resize((self.width, self.height), Image.Resampling.LANCZOS)

    def render_broadcast_slide(
        self,
        headline: str,
        beat_name: str,
        narration: str,
        category: str,
        region_label: str,
        source: str,
        save_path: Path,
        background_img: Optional[Image.Image] = None,
        slide_index: int = 1,
        total_slides: int = 12,
    ) -> str:
        """Render a broadcast-ready 1920x1080 Full HD graphic slide with distinct photographic visuals, chyron, and watermark."""
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Base Image: Either real background photo with cinematic contrast overlay, or a dynamic dark theme
        if background_img:
            base = self.resize_and_crop(background_img)
            # Apply cinematic gradient overlay to ensure text legibility while keeping photo vibrant
            overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            for y in range(self.height):
                if y < 200:
                    alpha = int(190 * (1 - y / 200))
                elif y > self.height - 300:
                    alpha = int(230 * ((y - (self.height - 300)) / 300))
                else:
                    alpha = 65  # subtle tint in middle so photo shines through
                draw_overlay.line([(0, y), (self.width, y)], fill=(6, 10, 20, alpha))
            base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        else:
            color_themes = [
                ((10, 18, 36), (15, 30, 60)),    # Deep Navy
                ((32, 12, 16), (65, 20, 25)),    # Breaking Crimson
                ((8, 28, 34), (14, 50, 62)),     # Tech Teal
                ((28, 22, 8), (55, 42, 16)),     # Amber Gold
                ((12, 32, 22), (22, 60, 42)),    # Emerald
                ((22, 14, 40), (45, 25, 75)),    # Indigo Violet
            ]
            c1, c2 = color_themes[(slide_index - 1) % len(color_themes)]
            base = Image.new("RGB", (self.width, self.height), c1)
            draw_bg = ImageDraw.Draw(base)
            for y in range(self.height):
                alpha = y / self.height
                r = int(c1[0] * (1 - alpha) + c2[0] * alpha)
                g = int(c1[1] * (1 - alpha) + c2[1] * alpha)
                b = int(c1[2] * (1 - alpha) + c2[2] * alpha)
                draw_bg.line([(0, y), (self.width, y)], fill=(r, g, b))

        draw = ImageDraw.Draw(base)

        # 2. Header Bar: Brand + Region/Category + Scene Indicator
        font_brand = self._get_font(30)
        draw.text((60, 45), "NEWS", font=font_brand, fill=(240, 245, 255))
        draw.text((150, 45), "INTEL", font=font_brand, fill=(0, 240, 255))

        # Slide progression indicator e.g. [SCENE 02/14]
        scene_tag = f"SCENE {slide_index:02d}/{total_slides:02d}"
        font_mono = self._get_font(18)
        draw.rectangle([(270, 48), (420, 80)], fill=(18, 28, 48), outline=(0, 240, 255), width=2)
        draw.text((282, 53), scene_tag, font=font_mono, fill=(0, 240, 255))

        # Pill tag for region and category
        pill_text = f"● {region_label} // {category.upper()}"
        font_pill = self._get_font(20)
        pill_w = len(pill_text) * 11 + 30
        draw.rounded_rectangle([(self.width - pill_w - 60, 40), (self.width - 60, 85)], radius=8, fill=(10, 20, 40), outline=(0, 200, 255), width=2)
        draw.text((self.width - pill_w - 45, 50), pill_text, font=font_pill, fill=(0, 240, 255))

        # 3. Main Headline (wrapped at top)
        font_title = self._get_font(44)
        words = headline.split()
        lines = []
        curr_line = []
        for w in words:
            curr_line.append(w)
            if len(" ".join(curr_line)) > 55:
                lines.append(" ".join(curr_line))
                curr_line = []
        if curr_line:
            lines.append(" ".join(curr_line))

        y_offset = 110
        for l in lines[:2]:
            draw.text((63, y_offset + 3), l, font=font_title, fill=(0, 0, 0))
            draw.text((60, y_offset), l, font=font_title, fill=(255, 255, 255))
            y_offset += 54

        # 4. Narration Subtitle Box (Lower Third - 1080p scaled)
        lower_third_top = self.height - 260
        draw.rectangle([(0, lower_third_top), (self.width, self.height)], fill=(4, 7, 14))

        bar_colors = [(0, 240, 255), (255, 60, 60), (0, 200, 255), (245, 158, 11), (16, 185, 129), (99, 102, 241)]
        accent_color = bar_colors[(slide_index - 1) % len(bar_colors)]
        draw.line([(0, lower_third_top), (self.width, lower_third_top)], fill=accent_color, width=6)

        # Beat Badge
        font_badge = self._get_font(20)
        badge_w = len(beat_name) * 12 + 32
        draw.rectangle([(60, lower_third_top + 20), (60 + badge_w, lower_third_top + 60)], fill=accent_color)
        draw.text((74, lower_third_top + 28), beat_name.upper(), font=font_badge, fill=(5, 10, 20))

        # Source badge
        draw.text((74 + badge_w + 20, lower_third_top + 30), f"SOURCE: {source}", font=font_badge, fill=(160, 180, 210))

        # Subtitle speech narration (wrapped)
        font_narration = self._get_font(28)
        n_words = narration.split()
        n_lines = []
        c_line = []
        for nw in n_words:
            c_line.append(nw)
            if len(" ".join(c_line)) > 75:
                n_lines.append(" ".join(c_line))
                c_line = []
        if c_line:
            n_lines.append(" ".join(c_line))

        ny_offset = lower_third_top + 80
        for nl in n_lines[:3]:
            draw.text((60, ny_offset), nl, font=font_narration, fill=(240, 245, 255))
            ny_offset += 42

        # Save image
        base.save(str(save_path), "JPEG", quality=95)
        return str(save_path)


def verify_image_with_nvidia_vision(img: Image.Image, story_title: str) -> bool:
    """Evaluate image suitability using NVIDIA meta/llama-3.2-11b-vision-instruct.
    STRICT FAIL-CLOSED: Rejects outside products, cartoons, ads, irrelevant cars/merchandise.
    Returns False on any error or rejection.
    """
    if not settings.NVIDIA_API_KEY:
        return False
    try:
        import base64
        import json
        import requests

        thumb = img.copy()
        thumb.thumbnail((512, 512))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"

        clean_topic = story_title[:150]
        prompt = (
            f"You are a strict television news standards director.\n"
            f"Evaluate if this image is suitable as authentic editorial news imagery for a television broadcast about: \"{clean_topic}\".\n\n"
            f"STRICT REJECTION RULES (Must reject immediately if ANY apply):\n"
            f"1. Reject if it shows commercial products, soda cans, energy drinks, snacks, mixers, or merchandise.\n"
            f"2. Reject if it shows sports cars, luxury supercars (e.g. Bugatti, Ferrari), or irrelevant vehicles unrelated to emergency services.\n"
            f"3. Reject if it shows cartoons, comic book superheroes, anime, memes, or clip art.\n"
            f"4. Reject if it shows women in lehengas, bridal jewellery, beauty pageants, or provocative fashion.\n"
            f"5. Reject if it is empty office furniture, irrelevant stock photos, or website UI screenshots.\n\n"
            f"Accept ONLY if the image depicts genuine news reporting context: flood rescue, emergency response, government leaders, press conferences, military, infrastructure, or relevant authentic scenes.\n\n"
            f"Respond strictly in JSON format: {{\"is_suitable\": true, \"reason\": \"...\"}} or {{\"is_suitable\": false, \"reason\": \"...\"}}"
        )

        headers = {
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": settings.NVIDIA_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "max_tokens": 120,
            "temperature": 0.1,
        }

        r = requests.post(
            f"{settings.NVIDIA_INTEGRATE_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=15,
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip().lower()
            if '"is_suitable": true' in content or '"is_suitable":true' in content:
                logger.info(f"NVIDIA Vision verified visual as SUITABLE for '{clean_topic[:40]}'")
                return True
            else:
                logger.warning(f"NVIDIA Vision REJECTED visual: {content[:100]}")
                return False
        else:
            logger.warning(f"NVIDIA Vision API returned status {r.status_code}")
            return False
    except Exception as e:
        logger.warning(f"NVIDIA Vision check failed (fail-closed): {e}")
        return False


def verify_image_with_gemini_vision(img: Image.Image, story_title: str) -> bool:
    """Evaluate image suitability using Gemini Vision with strict FAIL-CLOSED logic."""
    if not settings.GEMINI_API_KEY:
        return False
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        thumb = img.copy()
        thumb.thumbnail((512, 512))
        clean_topic = story_title[:150]
        prompt = (
            f"You are a strict broadcast news standards director.\n"
            f"Evaluate whether this image is suitable as background editorial imagery for a television news broadcast on: \"{clean_topic}\".\n"
            f"Reject commercial products, ads, soda cans, luxury cars, cartoons, comics, memes, or empty rooms.\n"
            f"Accept only authentic journalistic news context.\n"
            f"Answer in JSON: {{\"is_suitable\": true or false, \"reason\": \"brief reason\"}}"
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[thumb, prompt]
        )
        txt = resp.text.strip().lower()
        if '"is_suitable": true' in txt or '"is_suitable":true' in txt:
            return True
        logger.warning(f"Gemini Vision rejected visual: {resp.text.strip()[:100]}")
        return False
    except Exception as e:
        logger.warning(f"Gemini Vision check failed (fail-closed): {e}")
        return False


def verify_image_suitability(img: Image.Image, story_title: str) -> bool:
    """Dual-layer vision verification: NVIDIA Llama 3.2 Vision primary, Gemini Vision secondary.
    STRICT FAIL-CLOSED: Defaults to False if unverified or if any error occurs.
    """
    if settings.NVIDIA_API_KEY:
        nv_ok = verify_image_with_nvidia_vision(img, story_title)
        if nv_ok:
            return True
        return False

    if settings.GEMINI_API_KEY:
        return verify_image_with_gemini_vision(img, story_title)

    # Fail closed if no vision models are available
    return False

