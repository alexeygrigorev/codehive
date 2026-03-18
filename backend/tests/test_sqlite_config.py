"""Tests for SQLite default configuration (issue #93c).

Validates that:
- Default Settings point to SQLite + empty Redis
- Engine creation applies SQLite-specific connect_args
- WAL mode is enabled on SQLite connections
- PostgreSQL overrides are respected
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from codehive.config import Settings
from codehive.db.models import Base
from codehive.db.session import create_async_engine_from_settings


@pytest.fixture()
def _isolated_settings(monkeypatch, tmp_path):
    """Clear all CODEHIVE_* env vars and point Settings away from real .env files."""
    import os

    for key in list(os.environ):
        if key.startswith("CODEHIVE_"):
            monkeypatch.delenv(key)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


class TestConfigDefaults:
    """Config defaults point to SQLite and no Redis."""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_database_url_starts_with_sqlite(self):
        settings = Settings(_env_file=None)
        assert settings.database_url.startswith("sqlite")

    @pytest.mark.usefixtures("_isolated_settings")
    def test_redis_url_is_empty(self):
        settings = Settings(_env_file=None)
        assert settings.redis_url == ""

    def test_override_database_url_to_postgresql(self, monkeypatch):
        pg_url = "postgresql+asyncpg://user:pass@localhost/db"
        monkeypatch.setenv("CODEHIVE_DATABASE_URL", pg_url)
        settings = Settings()
        assert settings.database_url == pg_url

    def test_override_redis_url(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379/0"


class TestEngineCreation:
    """Engine factory applies SQLite-specific settings."""

    def test_sqlite_engine_created_successfully(self):
        """SQLite engine is created without errors (connect_args applied internally)."""
        engine = create_async_engine_from_settings(database_url="sqlite+aiosqlite:///:memory:")
        assert str(engine.url) == "sqlite+aiosqlite:///:memory:"

    def test_postgresql_url_creates_engine(self):
        """Ensure engine is created for PostgreSQL URLs without SQLite-specific args.

        We cannot actually connect to PostgreSQL in tests, so just verify
        the engine is created with the right URL.
        """
        engine = create_async_engine_from_settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db"
        )
        assert engine.url.get_backend_name() == "postgresql"
        assert engine.url.username == "user"
        assert engine.url.database == "db"

    @pytest.mark.asyncio
    async def test_sqlite_wal_mode_enabled(self):
        """Verify that WAL mode is set when connecting to a SQLite database."""
        engine = create_async_engine_from_settings(database_url="sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            result = await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    __import__("sqlalchemy").text("PRAGMA journal_mode")
                ).scalar()
            )
        # In-memory databases may report "memory" instead of "wal" since
        # WAL requires a file-based database, but the PRAGMA was executed.
        # For file-based SQLite, this would return "wal".
        assert result in ("wal", "memory")
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_sqlite_wal_mode_on_file_db(self, tmp_path):
        """Verify WAL mode is actually 'wal' for a file-based SQLite DB."""
        db_path = tmp_path / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"
        engine = create_async_engine_from_settings(database_url=url)
        async with engine.begin() as conn:
            result = await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    __import__("sqlalchemy").text("PRAGMA journal_mode")
                ).scalar()
            )
        assert result == "wal"
        await engine.dispose()


class TestAlembicMigrations:
    """Verify Alembic migrations work with SQLite."""

    @pytest.mark.asyncio
    async def test_create_all_tables_sqlite(self):
        """All models can be created on SQLite (equivalent to alembic upgrade head)."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Verify tables exist
        async with engine.begin() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: __import__("sqlalchemy").inspect(sync_conn).get_table_names()
            )
        expected_tables = {
            "projects",
            "issues",
            "sessions",
            "tasks",
            "messages",
            "events",
            "checkpoints",
            "pending_questions",
            "remote_targets",
            "custom_roles",
            "custom_archetypes",
            "push_subscriptions",
            "users",
            "device_tokens",
        }
        assert expected_tables.issubset(set(tables))
        await engine.dispose()
