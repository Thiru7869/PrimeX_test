"""
Gemini provider. The ONLY place in the codebase that knows how to talk to
Google's Gemini API. We call the REST API directly with httpx so we don't
depend on a fast-changing SDK.
"""
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.gateway.base import AIProvider, GenerationResult

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_CHAT_MODEL

    async def generate(self, messages: list[dict]) -> GenerationResult:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in your .env file.")

        # Gemini uses role "model" for the assistant and "user" for the user.
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]

        url = f"{self.BASE_URL}/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {"contents": contents}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            logger.error("gemini_error", status=resp.status_code, body=resp.text[:400])
            raise RuntimeError(f"Gemini API returned status {resp.status_code}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates (content may be blocked).")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")

        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        return GenerationResult(
            text=text, tokens=tokens, provider=self.name, model=self.model
        )