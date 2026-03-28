"""Tests for migration i9d0e1f2g3h4 (pipeline features).

Covers:
- Migration file structure (revision chain, upgrade/downgrade ops)
- Integration: upgrade, downgrade, re-upgrade on a fresh SQLite DB
"""

import importlib
import inspect
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture()
def migration_module():
    """Import the migration module for introspection."""
    spec = importlib.util.spec_from_file_location(
        "migration_147",
        Path(__file__).resolve().parent.parent
        / "codehive"
        / "db"
        / "migrations"
        / "versions"
        / "i9d0e1f2g3h4_pipeline_features.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Unit: migration file structure
# ---------------------------------------------------------------------------


class TestMigrationStructure:
    def test_revision_id(self, migration_module):
        assert migration_module.revision == "i9d0e1f2g3h4"

    def test_down_revision(self, migration_module):
        """Must depend on both heads (merge migration)."""
        down = migration_module.down_revision
        assert isinstance(down, tuple)
        assert "h8c9d0e1f2g3" in down
        assert "e6f7a8b9c0d1" in down

    def test_upgrade_adds_session_columns(self, migration_module):
        src = inspect.getsource(migration_module.upgrade)
        for col in ("role", "task_id", "pipeline_step"):
            assert col in src, f"upgrade() should add sessions.{col}"

    def test_upgrade_adds_tasks_pipeline_status(self, migration_module):
        src = inspect.getsource(migration_module.upgrade)
        assert "pipeline_status" in src

    def test_upgrade_creates_tables(self, migration_module):
        src = inspect.getsource(migration_module.upgrade)
        for table in ("task_pipeline_logs", "custom_roles", "custom_archetypes"):
            assert table in src, f"upgrade() should create {table}"

    def test_downgrade_drops_tables(self, migration_module):
        src = inspect.getsource(migration_module.downgrade)
        for table in ("task_pipeline_logs", "custom_roles", "custom_archetypes"):
            assert f'drop_table("{table}")' in src

    def test_downgrade_drops_columns(self, migration_module):
        src = inspect.getsource(migration_module.downgrade)
        for col in ("role", "task_id", "pipeline_step", "pipeline_status"):
            assert col in src, f"downgrade() should drop {col}"

    def test_downgrade_drops_fk_before_column(self, migration_module):
        """FK constraint must be dropped before the task_id column."""
        src = inspect.getsource(migration_module.downgrade)
        fk_pos = src.index("fk_sessions_task_id")
        col_pos = src.index('drop_column("sessions", "task_id")')
        assert fk_pos < col_pos, "FK should be dropped before the task_id column"


# ---------------------------------------------------------------------------
# Integration: Alembic upgrade / downgrade on fresh SQLite DB
# ---------------------------------------------------------------------------


def _run_alembic(db_path: str, *args: str) -> None:
    """Run an alembic command against a temporary SQLite database."""
    import os
    import subprocess

    env = os.environ.copy()
    env["CODEHIVE_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")


def _table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    names = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()
    return names


def _column_names(db_path: str, table: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


class TestAlembicIntegration:
    @pytest.fixture(autouse=True)
    def _tmp_db(self, tmp_path):
        self.db_path = str(tmp_path / "test.db")

    def test_upgrade_head_creates_pipeline_schema(self):
        _run_alembic(self.db_path, "upgrade", "head")

        tables = _table_names(self.db_path)
        assert "task_pipeline_logs" in tables
        assert "custom_roles" in tables
        assert "custom_archetypes" in tables

        sess_cols = _column_names(self.db_path, "sessions")
        assert "role" in sess_cols
        assert "task_id" in sess_cols
        assert "pipeline_step" in sess_cols

        task_cols = _column_names(self.db_path, "tasks")
        assert "pipeline_status" in task_cols

    def test_downgrade_removes_pipeline_schema(self):
        _run_alembic(self.db_path, "upgrade", "head")
        _run_alembic(self.db_path, "downgrade", "h8c9d0e1f2g3")

        tables = _table_names(self.db_path)
        assert "task_pipeline_logs" not in tables
        assert "custom_roles" not in tables
        assert "custom_archetypes" not in tables

        sess_cols = _column_names(self.db_path, "sessions")
        assert "role" not in sess_cols
        assert "task_id" not in sess_cols
        assert "pipeline_step" not in sess_cols

        task_cols = _column_names(self.db_path, "tasks")
        assert "pipeline_status" not in task_cols

    def test_re_upgrade_after_downgrade(self):
        _run_alembic(self.db_path, "upgrade", "head")
        _run_alembic(self.db_path, "downgrade", "h8c9d0e1f2g3")
        _run_alembic(self.db_path, "upgrade", "head")

        tables = _table_names(self.db_path)
        assert "task_pipeline_logs" in tables
        assert "custom_roles" in tables
        assert "custom_archetypes" in tables

    def test_single_head_after_upgrade(self):
        _run_alembic(self.db_path, "upgrade", "head")
        conn = sqlite3.connect(self.db_path)
        versions = [
            r[0] for r in conn.execute("SELECT version_num FROM alembic_version").fetchall()
        ]
        conn.close()
        assert versions == ["j0e1f2g3h4i5"], f"Expected single head, got {versions}"
