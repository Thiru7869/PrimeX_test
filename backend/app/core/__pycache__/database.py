"""
Database connection. Now ACTIVE because DATABASE_URL is set.
Creates the async engine + session, and a Base class for all models.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """All models (User, RefreshToken, ...) inherit from this."""
    pass


engine = None
AsyncSessionLocal = None

if settings.DATABASE_URL:
    # Neon requires an encrypted (SSL) connection. Local databases don't.
    is_local = ("localhost" in settings.DATABASE_URL) or ("127.0.0.1" in settings.DATABASE_URL)
    connect_args = {} if is_local else {"ssl": "require"}

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,     # prints SQL while learning
        pool_pre_ping=True,      # checks the connection is alive first
        connect_args=connect_args,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_db():
    """FastAPI dependency: one database session per request, always closed."""
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set. Add it to backend/.env")
    async with AsyncSessionLocal() as session:
        yield session