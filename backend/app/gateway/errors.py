"""
Custom exceptions so the Gateway can tell the difference between:
- a TEMPORARY failure (rate limit / overloaded) → worth retrying / falling back
- a PERMANENT failure (bad request) → don't retry, just fail
"""


class ProviderError(Exception):
    """Base class for provider failures."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProviderRateLimited(ProviderError):
    """429 / 503 — provider is busy or quota-exhausted. Retry, then fall back."""


class ProviderUnavailable(ProviderError):
    """Network error / 5xx — provider unreachable. Retry, then fall back."""


class ProviderBadRequest(ProviderError):
    """4xx (not 429) — our request was wrong. Do NOT retry or fall back blindly."""