"""
Database connection structure.

We set up the async SQLAlchemy engine and session here, plus a Base class
that all future database models will inherit from.

IMPORTANT: In this prompt we have no tables and no live database yet, so this
code only ACTIVATES if DATABASE_URL is set. The app runs fine without a DB
for now. We start using this for real in the next prompt.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """All future models (User, Chat, Message...) will inherit from this."""
    pass


# Only build the engine if a database URL is configured.
engine = None
AsyncSessionLocal = None

if settings.DATABASE_URL:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,     # log SQL while learning; turn off later
        pool_pre_ping=True,      # check connection is alive before using it
    )
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_db():
    """
    FastAPI dependency: gives each request its own database session,
    and always closes it afterward.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    async with AsyncSessionLocal() as session:
        yield session