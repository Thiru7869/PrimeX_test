"""
The AI Gateway. Right now it wraps a single provider (Gemini). In the next
prompt this becomes a list of providers with automatic fallback — and NONE of
the calling code (the ChatService) will need to change. That's the point of
having this abstraction.
"""
from app.gateway.base import GenerationResult
from app.gateway.providers.gemini_provider import GeminiProvider


class AIGateway:
    def __init__(self) -> None:
        self.provider = GeminiProvider()

    async def chat(self, messages: list[dict]) -> GenerationResult:
        return await self.provider.generate(messages)