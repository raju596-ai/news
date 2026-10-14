import logging
import asyncio
from typing import Tuple, Optional
from ..config import settings

logger = logging.getLogger(__name__)


class MultiProviderLLM:
    """Enterprise multi-provider LLM executor with automatic failover.

    Primary: Gemini ('gemini-3.8-flash')
    Fallback: Groq ('openai/gpt-oss-20b' / 'openai/gpt-oss-120b')
    """

    def __init__(self, primary_model: Optional[str] = None):
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.groq_api_key = settings.GROQ_API_KEY
        self.primary_model = primary_model or settings.PRIMARY_MODEL  # 'gemini-3.8-flash'
        self.gemini_fallback_model = settings.GEMINI_FALLBACK_MODEL  # 'gemini-3.5-flash'
        self.groq_primary_model = settings.FALLBACK_MODEL_GROQ  # 'openai/gpt-oss-20b'
        self.groq_secondary_model = settings.FALLBACK_MODEL_GROQ_SECONDARY  # 'openai/gpt-oss-120b'

    async def _call_gemini(self, system_message: str, prompt: str, model_name: str) -> str:
        """Call Google Gemini model with fast backoff retry for transient demand spikes."""
        import time
        from google import genai

        def _sync_call():
            client = genai.Client(api_key=self.gemini_api_key)
            full_prompt = f"System: {system_message}\n\nUser: {prompt}"
            last_err = None
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                    )
                    return response.text
                except Exception as e:
                    last_err = e
                    err_lower = str(e).lower()
                    if ("503" in err_lower or "unavailable" in err_lower or "high demand" in err_lower) and attempt == 0:
                        time.sleep(1.2)
                        continue
                    raise e
            raise last_err

        return await asyncio.to_thread(_sync_call)

    async def _call_groq(self, system_message: str, prompt: str, model_name: str) -> str:
        """Call Groq model."""
        from groq import Groq

        def _sync_call():
            client = Groq(api_key=self.groq_api_key)
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=4096,
            )
            return completion.choices[0].message.content

        return await asyncio.to_thread(_sync_call)

    async def generate(self, system_message: str, prompt: str) -> Tuple[str, str, bool]:
        """Execute text generation with primary model and automatic fallback on rate limit or error.

        Returns:
            Tuple[output_text, model_name_used, fallback_occurred]
        """
        fallback_occurred = False

        # 1. Attempt Primary: Gemini gemini-3.7-flash
        if self.gemini_api_key:
            try:
                logger.info(f"Invoking primary provider Gemini with model: {self.primary_model}")
                text = await self._call_gemini(system_message, prompt, self.primary_model)
                return text, f"Gemini ({self.primary_model})", False
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"Primary Gemini model {self.primary_model} encountered issue: {e}")

                # If rate limit (429) or quota exceeded, proceed directly to Groq fallback
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    logger.warning("[RATE LIMIT / QUOTA EXCEEDED] Gemini quota exhausted. Transitioning to Groq fallback.")
                else:
                    # For transient issues (e.g. 503 high demand spikes or model migration), try 2.5-flash or 3.6-flash
                    for alt_gemini in [settings.GEMINI_FALLBACK_MODEL, settings.GEMINI_TERTIARY_MODEL]:
                        try:
                            logger.info(f"Attempting alternative Gemini model: {alt_gemini}")
                            text = await self._call_gemini(system_message, prompt, alt_gemini)
                            return text, f"Gemini ({alt_gemini})", False
                        except Exception as gemini_alt_err:
                            logger.warning(f"Gemini {alt_gemini} alternative failed: {gemini_alt_err}")
                    logger.warning("All Gemini alternatives failed. Transitioning to Groq fallback.")

        # 2. Fallback: Groq
        fallback_occurred = True
        if self.groq_api_key:
            # Candidate Groq models to try in sequence based on user preference and account capability
            groq_candidates = [
                "openai/gpt-oss-120b",
                "llama-3.1-8b-instant",
                "openai/gpt-oss-20b",
                "qwen/qwen3.8-27b",
            ]
            last_groq_error = None
            for g_model in groq_candidates:
                try:
                    logger.info(f"Attempting Groq fallback model: {g_model}")
                    text = await self._call_groq(system_message, prompt, g_model)
                    return text, f"Groq ({g_model}) [Fallback]", True
                except Exception as g_err:
                    logger.warning(f"Groq model {g_model} failed: {g_err}")
                    last_groq_error = g_err

            raise RuntimeError(f"All Groq models failed. Last error: {last_groq_error}")

        raise RuntimeError("No valid LLM provider API keys available or all providers failed.")


llm_service = MultiProviderLLM()
