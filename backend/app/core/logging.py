"""
Structured logging setup.

In development we print colorful, human-readable logs.
In production we print JSON logs (easy for tools to read).
We use structlog because plain print() statements don't scale.
"""
import logging
import structlog

from app.core.config import settings


def setup_logging() -> None:
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(format="%(message)s", level=log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            # Pretty console in dev, JSON in production:
            structlog.dev.ConsoleRenderer()
            if settings.DEBUG
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)