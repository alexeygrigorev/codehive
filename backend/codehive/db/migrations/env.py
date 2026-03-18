"""Alembic environment configuration — async engine support (PostgreSQL & SQLite)."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import all models so that Base.metadata is fully populated.
from codehive.db.models import Base  # noqa: F401

# Alembic Config object.
config = context.config

# Override sqlalchemy.url from Settings so the database URL is always
# read from the canonical application configuration (env vars / .env).
from codehive.config import Settings  # noqa: E402

_settings = Settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)

# Set up Python logging from the .ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    url = config.get_main_option("sqlalchemy.url")
    engine_kwargs: dict = {"poolclass": pool.NullPool}
    if url and url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    connectable = create_async_engine(url, **engine_kwargs)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — delegates to async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
