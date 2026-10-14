"""Dedicated High-CTR YouTube Thumbnail Generator.
Renders mobile-optimized 1280x720 thumbnails with high-contrast typography,
urgent news badge, and focal visual treatment to maximize click-through rate.
"""

import re
import logging
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from ..base import NewsStory
from ...config import settings
from ...tools.news_fetcher import sanitize_news_headline

logger = logging.getLogger(__name__)


class YouTubeThumbnailGenerator:
    """Creates clickable, high-contrast 1280x720 thumbnails designed for YouTube mobile feeds."""

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

    def _get_font(self, size: int, bold: bool = True) -> ImageFont.ImageFont:
        font_names = (
            ["impact.ttf", "arialbd.ttf", "segoeui.ttf", "tahomabd.ttf"]
            if bold
            else ["segoeui.ttf", "arial.ttf"]
        )
        for fn in font_names:
            try:
                return ImageFont.truetype(fn, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _extract_punchy_hook(self, title: str) -> list[str]:
        """Extract a short, high-curiosity 3-5 word hook split into 2 punchy lines."""
        clean = sanitize_news_headline(title)
        clean = re.sub(r"[^\w\s-]", "", clean).strip()

        words = clean.split()
        if not words:
            return ["BREAKING", "SPECIAL REPORT"]

        # If title is short (<= 6 words), split in half
        if len(words) <= 6:
            mid = max(1, len(words) // 2)
            return [" ".join(words[:mid]).upper(), " ".join(words[mid:]).upper()]

        # For longer titles, pick core action/entity words
        first_line = " ".join(words[:3]).upper()
        second_line = " ".join(words[3:6]).upper()
        return [first_line, second_line]

    def render_thumbnail(
        self,
        story: NewsStory,
        lead_image_path: Optional[Path] = None,
        save_path: Optional[Path] = None,
    ) -> Path:
        """Render the 1280x720 thumbnail and save to disk."""
        if save_path is None:
            save_path = settings.MEDIA_DIR / story.id / "thumbnail.jpg"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Base Image
        base = None
        if lead_image_path and lead_image_path.exists():
            try:
                base = Image.open(lead_image_path).convert("RGB")
            except Exception as e:
                logger.debug(f"Could not open lead image for thumbnail: {e}")

        if base is None:
            # Fallback high-contrast dark gradient
            base = Image.new("RGB", (self.width, self.height), (12, 18, 32))
            draw_bg = ImageDraw.Draw(base)
            for y in range(self.height):
                alpha = y / self.height
                r = int(10 * (1 - alpha) + 26 * alpha)
                g = int(16 * (1 - alpha) + 40 * alpha)
                b = int(32 * (1 - alpha) + 72 * alpha)
                draw_bg.line([(0, y), (self.width, y)], fill=(r, g, b))
        else:
            # Resize and crop to 1280x720
            target_ratio = self.width / self.height
            img_ratio = base.width / base.height
            if img_ratio > target_ratio:
                new_w = int(base.height * target_ratio)
                left = (base.width - new_w) // 2
                base = base.crop((left, 0, left + new_w, base.height))
            else:
                new_h = int(base.width / target_ratio)
                top = (base.height - new_h) // 2
                base = base.crop((0, top, base.width, top + new_h))
            base = base.resize((self.width, self.height), Image.Resampling.LANCZOS)

            # Boost contrast (+20%) and saturation (+15%) for mobile screen pop
            enhancer = ImageEnhance.Contrast(base)
            base = enhancer.enhance(1.22)
            color_enhancer = ImageEnhance.Color(base)
            base = color_enhancer.enhance(1.18)

        # 2. Add cinematic contrast gradient overlay
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Dark gradient from bottom up and top-left vignette
        for y in range(self.height):
            if y > self.height - 380:
                alpha = int(225 * ((y - (self.height - 380)) / 380))
                draw_ov.line([(0, y), (self.width, y)], fill=(4, 7, 14, alpha))
            elif y < 140:
                alpha = int(160 * (1 - y / 140))
                draw_ov.line([(0, y), (self.width, y)], fill=(2, 4, 10, alpha))

        # Dark translucent panel on left side for text legibility
        for x in range(int(self.width * 0.75)):
            alpha = int(140 * (1 - x / (self.width * 0.75)))
            draw_ov.line([(x, 0), (x, self.height)], fill=(2, 6, 12, alpha))

        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        # 3. Breaking News Pill Badge (Top Left)
        font_badge = self._get_font(26, bold=True)
        badge_text = "● BREAKING NEWS"
        draw.rounded_rectangle([(50, 45), (320, 95)], radius=8, fill=(220, 20, 20), outline=(255, 60, 60), width=2)
        draw.text((70, 56), badge_text, font=font_badge, fill=(255, 255, 255))

        # Category pill (Top Right)
        font_cat = self._get_font(22, bold=True)
        cat_text = f"{story.category.upper()} // {story.region.value.upper()}"
        cat_w = len(cat_text) * 12 + 40
        draw.rounded_rectangle([(self.width - cat_w - 50, 45), (self.width - 50, 95)], radius=8, fill=(10, 20, 40), outline=(0, 220, 255), width=2)
        draw.text((self.width - cat_w - 30, 56), cat_text, font=font_cat, fill=(0, 230, 255))

        # 4. Massive Dual-Tone Headline Hook (Bottom Left)
        hook_lines = self._extract_punchy_hook(story.title)
        font_hook = self._get_font(68, bold=True)

        y_pos = self.height - 240
        colors = [(255, 255, 255), (255, 215, 0)]  # White line 1, Vibrant Gold line 2

        for idx, line in enumerate(hook_lines[:2]):
            line_color = colors[idx % len(colors)]
            # Draw heavy black shadow for 100% legibility on any background
            for ox in [-3, -2, -1, 1, 2, 3]:
                for oy in [-3, -2, -1, 1, 2, 3]:
                    draw.text((50 + ox, y_pos + oy), line, font=font_hook, fill=(0, 0, 0))
            draw.text((50, y_pos), line, font=font_hook, fill=line_color)
            y_pos += 76

        # 5. Bottom Glowing Cyan Accent Strip
        draw.rectangle([(0, self.height - 8), (self.width, self.height)], fill=(0, 230, 255))

        base.save(str(save_path), "JPEG", quality=95)
        logger.info(f"YouTubeThumbnailGenerator: Rendered high-CTR thumbnail at {save_path}")
        return save_path

    def render_thumbnail_b(
        self,
        story: NewsStory,
        lead_image_path: Optional[Path] = None,
        save_path: Optional[Path] = None,
    ) -> Path:
        """Render Option B: High-Voltage curiosity-focused thumbnail with Amber/Cyan styling."""
        if save_path is None:
            save_path = settings.MEDIA_DIR / story.id / "thumbnail_b.jpg"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Base Image
        base = None
        if lead_image_path and lead_image_path.exists():
            try:
                base = Image.open(lead_image_path).convert("RGB")
            except Exception as e:
                logger.debug(f"Could not open lead image for thumbnail B: {e}")

        if base is None:
            base = Image.new("RGB", (self.width, self.height), (15, 12, 28))
            draw_bg = ImageDraw.Draw(base)
            for y in range(self.height):
                alpha = y / self.height
                r = int(24 * (1 - alpha) + 12 * alpha)
                g = int(20 * (1 - alpha) + 38 * alpha)
                b = int(48 * (1 - alpha) + 68 * alpha)
                draw_bg.line([(0, y), (self.width, y)], fill=(r, g, b))
        else:
            target_ratio = self.width / self.height
            img_ratio = base.width / base.height
            if img_ratio > target_ratio:
                new_w = int(base.height * target_ratio)
                left = (base.width - new_w) // 2
                base = base.crop((left, 0, left + new_w, base.height))
            else:
                new_h = int(base.width / target_ratio)
                top = (base.height - new_h) // 2
                base = base.crop((0, top, base.width, top + new_h))
            base = base.resize((self.width, self.height), Image.Resampling.LANCZOS)

            # High drama saturation & contrast boost
            base = ImageEnhance.Contrast(base).enhance(1.28)
            base = ImageEnhance.Color(base).enhance(1.22)

        # 2. Cinematic Dual-Vignette Overlay
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        for y in range(self.height):
            if y > self.height - 350:
                alpha = int(235 * ((y - (self.height - 350)) / 350))
                draw_ov.line([(0, y), (self.width, y)], fill=(6, 8, 16, alpha))
            elif y < 130:
                alpha = int(170 * (1 - y / 130))
                draw_ov.line([(0, y), (self.width, y)], fill=(4, 6, 12, alpha))

        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        # 3. High-Voltage Yellow Pill Badge (Top Left)
        font_badge = self._get_font(26, bold=True)
        badge_text = "⚡ SPECIAL REPORT"
        draw.rounded_rectangle([(50, 45), (340, 95)], radius=8, fill=(230, 160, 0), outline=(255, 210, 40), width=2)
        draw.text((70, 56), badge_text, font=font_badge, fill=(0, 0, 0))

        # 4. Region & Live Intel Pill (Top Right)
        font_cat = self._get_font(22, bold=True)
        cat_text = f"LIVE // {story.region.value.upper()}"
        cat_w = len(cat_text) * 12 + 40
        draw.rounded_rectangle([(self.width - cat_w - 50, 45), (self.width - 50, 95)], radius=8, fill=(15, 25, 45), outline=(255, 200, 0), width=2)
        draw.text((self.width - cat_w - 30, 56), cat_text, font=font_cat, fill=(255, 215, 0))

        # 5. Bold Center-Bottom Headline Hook
        hook_lines = self._extract_punchy_hook(story.title)
        font_hook = self._get_font(72, bold=True)
        y_pos = self.height - 230
        colors = [(255, 220, 0), (255, 255, 255)]  # Gold line 1, Crisp White line 2

        for idx, line in enumerate(hook_lines[:2]):
            line_color = colors[idx % len(colors)]
            for ox in [-3, -2, -1, 1, 2, 3]:
                for oy in [-3, -2, -1, 1, 2, 3]:
                    draw.text((50 + ox, y_pos + oy), line, font=font_hook, fill=(0, 0, 0))
            draw.text((50, y_pos), line, font=font_hook, fill=line_color)
            y_pos += 80

        # Gold Glowing Bottom Accent Strip
        draw.rectangle([(0, self.height - 8), (self.width, self.height)], fill=(255, 200, 0))

        base.save(str(save_path), "JPEG", quality=95)
        logger.info(f"YouTubeThumbnailGenerator: Rendered high-CTR thumbnail Option B at {save_path}")
        return save_path

    def render_ab_thumbnails(
        self,
        story: NewsStory,
        lead_image_path: Optional[Path] = None,
        save_dir: Optional[Path] = None,
    ) -> tuple[Path, Path]:
        """Render both Option A and Option B thumbnails for A/B testing."""
        if save_dir is None:
            save_dir = settings.MEDIA_DIR / story.id
        save_dir.mkdir(parents=True, exist_ok=True)

        path_a = save_dir / "thumbnail.jpg"
        path_b = save_dir / "thumbnail_b.jpg"

        self.render_thumbnail(story, lead_image_path, save_path=path_a)
        self.render_thumbnail_b(story, lead_image_path, save_path=path_b)

        story.media.thumbnail_path = str(path_a)
        story.media.thumbnail_b_path = str(path_b)
        return path_a, path_b
