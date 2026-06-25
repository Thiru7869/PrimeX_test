from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = None
AsyncSessionLocal = None

if settings.DATABASE_URL:
    is_local = (
        "localhost" in settings.DATABASE_URL
        or "127.0.0.1" in settings.DATABASE_URL
    )

    connect_args = {} if is_local else {"ssl": "require"}

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db():
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to backend/.env"
        )

    async with AsyncSessionLocal() as session:
        yield session