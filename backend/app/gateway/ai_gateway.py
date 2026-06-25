"""
The resilient AI Gateway.
Tries providers in priority order. Each provider already retries internally on
temporary errors. If a provider still fails, we put it on a short cooldown and
fall through to the next one. Every attempt is logged to provider_usage.

NOTE: ChatService calls `gateway.chat(messages, user_id, db)` — we add optional
db/user_id so we can log usage. If they're omitted, logging is simply skipped.
"""
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.gateway.base import GenerationResult
from app.gateway.errors import ProviderError
from app.gateway.providers.gemini_provider import GeminiProvider
from app.gateway.providers.groq_provider import GroqProvider
from app.models.provider_usage import ProviderUsage

logger = get_logger(__name__)

# Simple in-memory cooldown store: { "gemini": datetime_until }.
# (In-memory is fine for a single instance; we make it a real table later.)
_cooldowns: dict[str, datetime] = {}


class AIGateway:
    def __init__(self) -> None:
        # Priority order: Gemini first, Groq as fallback.
        self.providers = [GeminiProvider(), GroqProvider()]

    def _in_cooldown(self, name: str) -> bool:
        until = _cooldowns.get(name)
        return until is not None and datetime.now(timezone.utc) < until

    def _set_cooldown(self, name: str) -> None:
        _cooldowns[name] = datetime.now(timezone.utc) + timedelta(
            seconds=settings.PROVIDER_COOLDOWN_SECONDS
        )

    async def _log(self, db, user_id, provider, model, latency_ms, tokens, status, error_type):
        if db is None:
            return
        db.add(ProviderUsage(
            user_id=user_id, provider=provider, model=model, operation="chat",
            latency_ms=latency_ms, tokens=tokens, status=status, error_type=error_type,
        ))
        # We flush (not commit) — the caller's transaction owns the commit.
        await db.flush()

    async def chat(
        self,
        messages: list[dict],
        user_id=None,
        db: AsyncSession | None = None,
    ) -> GenerationResult:
        last_error: Exception | None = None
        attempted_any = False

        for index, provider in enumerate(self.providers):
            if not provider.is_configured():
                continue
            if self._in_cooldown(provider.name):
                logger.info("provider_skipped_cooldown", provider=provider.name)
                continue

            attempted_any = True
            start = time.perf_counter()
            try:
                result = await provider.generate(messages)
                latency = int((time.perf_counter() - start) * 1000)
                # status "success" if first choice, "fallback" if a later one.
                status = "success" if index == 0 else "fallback"
                await self._log(db, user_id, provider.name, result.model,
                                latency, result.tokens, status, None)
                logger.info("provider_success", provider=provider.name, status=status)
                return result
            except ProviderError as exc:
                latency = int((time.perf_counter() - start) * 1000)
                last_error = exc
                self._set_cooldown(provider.name)
                await self._log(db, user_id, provider.name, None, latency, 0,
                                "fail", type(exc).__name__)
                logger.warning("provider_failed", provider=provider.name,
                               error=str(exc), next="fallback")
                continue  # try the next provider

        if not attempted_any:
            raise ProviderError("No AI provider is configured. Check your API keys.")
        raise last_error or ProviderError("All providers failed.")