"""
Alembic environment. Connects Alembic to our app's database URL and models.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from app.core.config import settings
from app.core.database import Base
# Importing the models package registers every table on Base.metadata
# so that --autogenerate can detect them.

from app.models import User, RefreshToken, Chat, Message, ProviderUsage  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    is_local = ("localhost" in settings.DATABASE_URL) or ("127.0.0.1" in settings.DATABASE_URL)
    connect_args = {} if is_local else {"ssl": "require"}

    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# We always run "online" (connected to the real DB).
run_migrations_online()