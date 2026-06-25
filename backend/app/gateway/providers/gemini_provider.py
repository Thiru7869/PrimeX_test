"""Gemini provider. Talks to Google's Gemini REST API with retry on temporary errors."""
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.gateway.base import AIProvider, GenerationResult
from app.gateway.errors import (
    ProviderBadRequest, ProviderRateLimited, ProviderUnavailable,
)
from app.gateway.retry import with_retry

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_CHAT_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @with_retry
    async def generate(self, messages: list[dict]) -> GenerationResult:
        if not self.api_key:
            raise ProviderBadRequest("GEMINI_API_KEY is not set.")

        contents = [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        url = f"{self.BASE_URL}/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json={"contents": contents}, headers=headers)
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"Network error: {exc}")

        if resp.status_code == 429:
            raise ProviderRateLimited("Gemini quota exceeded", 429)
        if resp.status_code in (500, 502, 503, 504):
            raise ProviderUnavailable(f"Gemini overloaded ({resp.status_code})", resp.status_code)
        if resp.status_code != 200:
            raise ProviderBadRequest(f"Gemini error {resp.status_code}: {resp.text[:200]}",
                                     resp.status_code)

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderBadRequest("Gemini returned no candidates (blocked content).")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise ProviderBadRequest("Gemini returned an empty response.")

        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        return GenerationResult(text=text, tokens=tokens, provider=self.name, model=self.model)