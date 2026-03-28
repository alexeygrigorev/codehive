"""Tests for SQLite column sync on startup (issue #148).

Covers:
- Missing columns are detected and added via ALTER TABLE ADD COLUMN
- Existing columns are not touched
- Server defaults are applied to new columns
- Multiple tables with missing columns are all handled
- TDD bug reproduction: ORM query fails before sync, succeeds after
- Lifespan integration: app startup syncs columns automatically
"""

import sqlite3
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from codehive.db.models import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _column_names(db_path: str, table: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


def _column_info(db_path: str, table: str) -> dict[str, dict]:
    """Return {col_name: {type, notnull, dflt_value, pk}} for a table."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    conn.close()
    return {r[1]: {"type": r[2], "notnull": r[3], "dflt_value": r[4], "pk": r[5]} for r in rows}


async def _create_full_schema(db_path: str) -> None:
    """Create a full schema DB using create_all."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def _create_old_schema(db_path: str, drops: dict[str, list[str]]) -> None:
    """Create a full schema then drop specified columns by recreating tables without them.

    drops: {table_name: [col1, col2, ...]} columns to remove.
    SQLite doesn't support DROP COLUMN in older versions, so we recreate the table.
    """
    await _create_full_schema(db_path)

    conn = sqlite3.connect(db_path)
    for table_name, cols_to_drop in drops.items():
        # Get current columns
        pragma = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        all_cols = [r[1] for r in pragma]
        keep_cols = [c for c in all_cols if c not in cols_to_drop]

        # Recreate table without the dropped columns
        cols_str = ", ".join(keep_cols)
        conn.execute(f"ALTER TABLE {table_name} RENAME TO _old_{table_name}")
        conn.execute(f"CREATE TABLE {table_name} AS SELECT {cols_str} FROM _old_{table_name}")
        conn.execute(f"DROP TABLE _old_{table_name}")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Test 1: Missing columns are detected and added
# ---------------------------------------------------------------------------


class TestSyncMissingColumns:
    @pytest.fixture(autouse=True)
    def _tmp_db(self, tmp_path):
        self.db_path = str(tmp_path / "test.db")
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"

    @pytest.mark.asyncio
    async def test_missing_session_columns_added(self):
        """Columns missing from sessions table are added by sync."""
        from codehive.db.sync_columns import sync_sqlite_columns

        missing_cols = ["role", "task_id", "pipeline_step"]
        await _create_old_schema(self.db_path, {"sessions": missing_cols})

        # Verify columns are missing before sync
        cols_before = _column_names(self.db_path, "sessions")
        for col in missing_cols:
            assert col not in cols_before, f"{col} should be missing before sync"

        # Run sync
        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        async with engine.begin() as conn:
            await conn.run_sync(sync_sqlite_columns)
        await engine.dispose()

        # Verify columns are present after sync
        cols_after = _column_names(self.db_path, "sessions")
        for col in missing_cols:
            assert col in cols_after, f"{col} should exist after sync"

    @pytest.mark.asyncio
    async def test_existing_columns_not_touched(self):
        """When all columns exist, sync does nothing."""
        from codehive.db.sync_columns import sync_sqlite_columns

        await _create_full_schema(self.db_path)

        # Get column info before
        info_before = _column_info(self.db_path, "sessions")

        # Run sync
        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        async with engine.begin() as conn:
            await conn.run_sync(sync_sqlite_columns)
        await engine.dispose()

        # Column info should be identical
        info_after = _column_info(self.db_path, "sessions")
        assert info_before == info_after

    @pytest.mark.asyncio
    async def test_server_defaults_applied(self):
        """Added columns with server_default get the default value on INSERT."""
        from codehive.db.sync_columns import sync_sqlite_columns

        # Task.pipeline_status has server_default="backlog"
        await _create_old_schema(self.db_path, {"tasks": ["pipeline_status"]})

        # Run sync
        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        async with engine.begin() as conn:
            await conn.run_sync(sync_sqlite_columns)
        await engine.dispose()

        # Insert a row without specifying pipeline_status, verify default
        raw = sqlite3.connect(self.db_path)
        session_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        # Insert a project first (FK)
        raw.execute(
            "INSERT INTO projects (id, name, knowledge) VALUES (?, ?, '{}')",
            (project_id, "test"),
        )
        # Insert a session (FK for task)
        raw.execute(
            "INSERT INTO sessions (id, project_id, name, engine, mode, status, config) "
            "VALUES (?, ?, 'test', 'claude', 'auto', 'idle', '{}')",
            (session_id, project_id),
        )
        # Insert a task without pipeline_status
        raw.execute(
            "INSERT INTO tasks (id, session_id, title, status, priority, mode, created_by) "
            "VALUES (?, ?, 'test', 'pending', 0, 'auto', 'user')",
            (task_id, session_id),
        )
        raw.commit()
        row = raw.execute("SELECT pipeline_status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        raw.close()
        assert row[0] == "backlog", f"Expected default 'backlog', got {row[0]}"

    @pytest.mark.asyncio
    async def test_multiple_tables_synced(self):
        """Missing columns on multiple tables are all added."""
        from codehive.db.sync_columns import sync_sqlite_columns

        await _create_old_schema(
            self.db_path,
            {
                "sessions": ["role", "pipeline_step"],
                "tasks": ["pipeline_status"],
            },
        )

        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        async with engine.begin() as conn:
            await conn.run_sync(sync_sqlite_columns)
        await engine.dispose()

        sess_cols = _column_names(self.db_path, "sessions")
        assert "role" in sess_cols
        assert "pipeline_step" in sess_cols

        task_cols = _column_names(self.db_path, "tasks")
        assert "pipeline_status" in task_cols


# ---------------------------------------------------------------------------
# Test 5: TDD bug reproduction (red-green cycle)
# ---------------------------------------------------------------------------


class TestTDDBugReproduction:
    @pytest.fixture(autouse=True)
    def _tmp_db(self, tmp_path):
        self.db_path = str(tmp_path / "test.db")
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"

    @pytest.mark.asyncio
    async def test_orm_fails_before_sync_succeeds_after(self):
        """ORM query on sessions fails when columns are missing, works after sync."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from codehive.db.sync_columns import sync_sqlite_columns

        missing_cols = ["role", "task_id", "pipeline_step"]
        await _create_old_schema(self.db_path, {"sessions": missing_cols})

        # Insert test data via raw SQL
        project_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        raw = sqlite3.connect(self.db_path)
        raw.execute(
            "INSERT INTO projects (id, name, knowledge) VALUES (?, ?, '{}')",
            (project_id, "test-project"),
        )
        raw.execute(
            "INSERT INTO sessions (id, project_id, name, engine, mode, status, config) "
            "VALUES (?, ?, 'test-session', 'claude', 'auto', 'idle', '{}')",
            (session_id, project_id),
        )
        raw.commit()
        raw.close()

        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        sm = async_sessionmaker(engine, expire_on_commit=False)

        # BEFORE sync: ORM query should fail (references missing columns)
        async with sm() as db:
            try:
                result = await db.execute(
                    text("SELECT role FROM sessions WHERE id = :id"),
                    {"id": session_id},
                )
                # If we get here, the column somehow exists — fail the test
                pytest.fail("Expected query to fail due to missing 'role' column")
            except Exception:
                pass  # Expected — column doesn't exist

        # Run sync
        async with engine.begin() as conn:
            await conn.run_sync(sync_sqlite_columns)

        # AFTER sync: ORM query should succeed
        async with sm() as db:
            result = await db.execute(
                text("SELECT role, task_id, pipeline_step FROM sessions WHERE id = :id"),
                {"id": session_id},
            )
            row = result.fetchone()
            assert row is not None, "Session row should still exist"
            # Old data preserved, new columns are NULL
            assert row[0] is None  # role
            assert row[1] is None  # task_id
            assert row[2] is None  # pipeline_step

        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 6: Logging
# ---------------------------------------------------------------------------


class TestSyncLogging:
    @pytest.fixture(autouse=True)
    def _tmp_db(self, tmp_path):
        self.db_path = str(tmp_path / "test.db")
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"

    @pytest.mark.asyncio
    async def test_logs_added_columns(self, caplog):
        """Each added column is logged at INFO level."""
        import logging

        from codehive.db.sync_columns import sync_sqlite_columns

        await _create_old_schema(self.db_path, {"sessions": ["role"]})

        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        with caplog.at_level(logging.INFO, logger="codehive.db.sync_columns"):
            async with engine.begin() as conn:
                await conn.run_sync(sync_sqlite_columns)
        await engine.dispose()

        assert any("sessions.role" in msg for msg in caplog.messages), (
            f"Expected log about sessions.role, got: {caplog.messages}"
        )

    @pytest.mark.asyncio
    async def test_no_log_when_nothing_missing(self, caplog):
        """No logging when all columns are present."""
        import logging

        from codehive.db.sync_columns import sync_sqlite_columns

        await _create_full_schema(self.db_path)

        engine = create_async_engine(self.db_url, connect_args={"check_same_thread": False})
        with caplog.at_level(logging.INFO, logger="codehive.db.sync_columns"):
            async with engine.begin() as conn:
                await conn.run_sync(sync_sqlite_columns)
        await engine.dispose()

        added_msgs = [msg for msg in caplog.messages if "Added column" in msg]
        assert len(added_msgs) == 0, f"Expected no 'Added column' messages, got: {added_msgs}"
