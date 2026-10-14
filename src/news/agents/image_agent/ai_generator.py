"""AI News Image Generator Agent
Generates realistic news imagery using state-of-the-art text-to-image models.
Supports Qwen-Image-2.1 with automatic fallback to FLUX.1-schnell and SDXL via Hugging Face.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from PIL import Image
from ...config import settings

logger = logging.getLogger(__name__)

# Preferred model hierarchy
MODELS_TO_TRY = [
    "Qwen/Qwen-Image-2.1",
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
]


class AINewsImageGenerator:
    """Generates authentic AI editorial news imagery from structured prompts."""

    def __init__(self):
        self.nvidia_api_key = settings.NVIDIA_API_KEY
        self.api_key = settings.HUGGING_API_KEY
        self._client = None
        if self.api_key:
            try:
                from huggingface_hub import InferenceClient
                self._client = InferenceClient(token=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize HuggingFace InferenceClient: {e}")

    def is_available(self) -> bool:
        return True

    def _sync_generate(self, prompt: str, model_name: Optional[str] = None) -> Optional[Image.Image]:
        """Synchronously query text-to-image models in order of priority:
        1. NVIDIA GenAI FLUX models (FLUX.1-schnell, FLUX.2-klein-4b, FLUX.1-dev).
        2. Pollinations SANA model (Zero-auth fallback, no x402 paywall).
        3. Hugging Face if configured and available.
        """
        import urllib.parse
        import urllib.request
        import io
        import base64
        import requests

        clean_prompt = prompt[:600].replace("\n", " ").strip()

        # 1. Primary: NVIDIA GenAI FLUX models
        if self.nvidia_api_key:
            models_to_query = []
            if model_name:
                models_to_query.append(model_name)
            # Add defaults as fallbacks
            for m in [settings.NVIDIA_IMAGE_MODEL, settings.NVIDIA_IMAGE_MODEL_FALLBACK, settings.NVIDIA_IMAGE_MODEL_TURBO]:
                if m not in models_to_query:
                    models_to_query.append(m)

            for nv_model in models_to_query:
                try:
                    logger.info(f"AINewsImageGenerator: Calling NVIDIA GenAI '{nv_model}' with prompt: '{clean_prompt[:60]}...'")
                    url = f"{settings.NVIDIA_GENAI_BASE_URL}/{nv_model}"
                    headers = {
                        "Authorization": f"Bearer {self.nvidia_api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    }
                    r = requests.post(url, headers=headers, json={"prompt": clean_prompt}, timeout=30)
                    if r.status_code == 200:
                        data = r.json()
                        artifacts = data.get("artifacts", [])
                        if artifacts and "base64" in artifacts[0]:
                            img_bytes = base64.b64decode(artifacts[0]["base64"])
                            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                            logger.info(f"AINewsImageGenerator: NVIDIA GenAI '{nv_model}' generated successfully ({img.size})")
                            return img
                    else:
                        logger.warning(f"NVIDIA GenAI '{nv_model}' returned status {r.status_code}: {r.text[:120]}")
                except Exception as e:
                    logger.warning(f"NVIDIA GenAI '{nv_model}' request error: {e}")

        # 2. Secondary: Pollinations SANA model (Zero-auth, bypasses x402 protocol)
        try:
            p_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(clean_prompt)}?width=1280&height=720&nologo=true&model=sana"
            logger.info(f"AINewsImageGenerator: Calling Pollinations SANA model...")
            req = urllib.request.Request(p_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsIntelBot/2.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read()
                if len(content) > 10000:
                    img = Image.open(io.BytesIO(content)).convert("RGB")
                    logger.info(f"AINewsImageGenerator: Pollinations SANA generated successfully ({img.size})")
                    return img
        except Exception as e:
            logger.debug(f"Pollinations SANA attempt error: {e}")

        # 3. Tertiary: Hugging Face models if client is active
        if self._client:
            for m_name in MODELS_TO_TRY:
                try:
                    logger.info(f"AINewsImageGenerator: Trying HF model '{m_name}'...")
                    img = self._client.text_to_image(clean_prompt, model=m_name)
                    if img:
                        return img
                except Exception as e:
                    if "402" in str(e) or "credits" in str(e).lower():
                        logger.debug("HF inference credits depleted.")
                        break
                    logger.debug(f"HF model '{m_name}' error: {e}")

        return None


    async def generate_image(self, prompt: str, save_path: Path, model_name: Optional[str] = None) -> Optional[Path]:
        """Generate a single 16:9 news image from a prompt and save to disk."""
        if not self.is_available():
            return None

        save_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            img = await asyncio.to_thread(self._sync_generate, prompt, model_name)
            if img:
                # Resize and crop to 16:9 (1920x1080)
                img = img.convert("RGB")
                target_w, target_h = settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT
                target_ratio = target_w / target_h
                img_ratio = img.width / img.height

                if img_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))

                final_img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                final_img.save(str(save_path), "JPEG", quality=95)
                return save_path
        except Exception as e:
            logger.error(f"AINewsImageGenerator: Generation failed for '{save_path.name}': {e}")
        return None

    async def generate_scene_images(
        self,
        scene_prompts: List[dict],
        output_dir: Path,
        max_images: int = 6,
        model_name: Optional[str] = None,
    ) -> List[Path]:
        """Throttled concurrent generation of realistic images for up to max_images scene beats."""
        if not self.is_available() or not scene_prompts:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        semaphore = asyncio.Semaphore(2)  # Limit concurrent calls to 2 to avoid throttling
        generated_paths: List[Path] = []

        async def _bounded_gen(idx: int, item: dict) -> Optional[Path]:
            beat = item.get("beat", f"scene_{idx}")
            prompt = item.get("prompt", "")
            if not prompt:
                return None
            p_path = output_dir / f"ai_gen_{idx}_{beat.lower().replace(' ', '_')}.jpg"
            async with semaphore:
                res = await self.generate_image(prompt, p_path, model_name=model_name)
                await asyncio.sleep(0.4)  # 400ms pause between requests
                return res

        tasks = [_bounded_gen(idx, item) for idx, item in enumerate(scene_prompts[:max_images])]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for p in results:
            if isinstance(p, Path) and p.exists():
                generated_paths.append(p)

        logger.info(f"AINewsImageGenerator: Successfully generated {len(generated_paths)} AI news images in {output_dir}")
        return generated_paths
