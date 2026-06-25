"""Groq provider. OpenAI-compatible chat API. Our fallback when Gemini fails."""
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.gateway.base import AIProvider, GenerationResult
from app.gateway.errors import (
    ProviderBadRequest, ProviderRateLimited, ProviderUnavailable,
)
from app.gateway.retry import with_retry

logger = get_logger(__name__)


class GroqProvider(AIProvider):
    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_CHAT_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @with_retry
    async def generate(self, messages: list[dict]) -> GenerationResult:
        if not self.api_key:
            raise ProviderBadRequest("GROQ_API_KEY is not set.")

        # Groq/OpenAI use "user"/"assistant" roles directly — no conversion needed.
        payload = {"model": self.model, "messages": messages}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self.URL, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"Network error: {exc}")

        if resp.status_code == 429:
            raise ProviderRateLimited("Groq rate limited", 429)
        if resp.status_code in (500, 502, 503, 504):
            raise ProviderUnavailable(f"Groq overloaded ({resp.status_code})", resp.status_code)
        if resp.status_code != 200:
            raise ProviderBadRequest(f"Groq error {resp.status_code}: {resp.text[:200]}",
                                     resp.status_code)

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ProviderBadRequest("Groq returned no choices.")
        text = (choices[0].get("message", {}).get("content") or "").strip()
        if not text:
            raise ProviderBadRequest("Groq returned an empty response.")

        tokens = data.get("usage", {}).get("total_tokens", 0)
        return GenerationResult(text=text, tokens=tokens, provider=self.name, model=self.model)