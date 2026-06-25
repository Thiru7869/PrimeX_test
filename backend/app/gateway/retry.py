"""
A retry wrapper using tenacity. It retries only on TEMPORARY errors
(rate-limited / unavailable), waiting longer each time: ~1s, 2s, 4s (+jitter).
A permanent ProviderBadRequest is NOT retried.
"""
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import settings
from app.gateway.errors import ProviderRateLimited, ProviderUnavailable


def with_retry(func):
    """Decorator: retry an async provider call on temporary failures."""
    return retry(
        retry=retry_if_exception_type((ProviderRateLimited, ProviderUnavailable)),
        stop=stop_after_attempt(settings.PROVIDER_MAX_RETRIES),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,  # after the last attempt, re-raise the real error
    )(func)