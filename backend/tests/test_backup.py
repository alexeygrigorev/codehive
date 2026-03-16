"""Tests for database backup functionality (issue #82)."""

import gzip
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codehive.core.backup import (
    BACKUP_FILENAME_PATTERN,
    create_backup,
    ensure_backup_dir,
    format_age,
    format_size,
    list_backups,
    parse_database_url,
    prune_backups,
    restore_backup,
)


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


class TestParseDatabaseUrl:
    def test_parse_asyncpg_url(self):
        url = "postgresql+asyncpg://myuser:mypass@db.host:5433/mydb"
        result = parse_database_url(url)
        assert result["host"] == "db.host"
        assert result["port"] == "5433"
        assert result["user"] == "myuser"
        assert result["password"] == "mypass"
        assert result["dbname"] == "mydb"

    def test_parse_plain_postgres_url(self):
        url = "postgresql://user:pass@localhost:5432/codehive"
        result = parse_database_url(url)
        assert result["host"] == "localhost"
        assert result["port"] == "5432"
        assert result["user"] == "user"
        assert result["password"] == "pass"
        assert result["dbname"] == "codehive"

    def test_parse_defaults(self):
        url = "postgresql://localhost/testdb"
        result = parse_database_url(url)
        assert result["host"] == "localhost"
        assert result["port"] == "5432"
        assert result["user"] == "codehive"
        assert result["password"] == ""
        assert result["dbname"] == "testdb"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestBackupConfig:
    def test_default_backup_dir(self):
        from codehive.config import Settings

        settings = Settings()
        assert settings.backup_dir == "./backups"

    def test_default_retention(self):
        from codehive.config import Settings

        settings = Settings()
        assert settings.backup_retention == 7

    def test_override_backup_dir(self, monkeypatch):
        from codehive.config import Settings

        monkeypatch.setenv("CODEHIVE_BACKUP_DIR", "/tmp/my-backups")
        settings = Settings()
        assert settings.backup_dir == "/tmp/my-backups"

    def test_override_retention(self, monkeypatch):
        from codehive.config import Settings

        monkeypatch.setenv("CODEHIVE_BACKUP_RETENTION", "14")
        settings = Settings()
        assert settings.backup_retention == 14


# ---------------------------------------------------------------------------
# Backup directory management
# ---------------------------------------------------------------------------


class TestEnsureBackupDir:
    def test_creates_directory(self, tmp_path):
        target = tmp_path / "new_dir" / "backups"
        result = ensure_backup_dir(str(target))
        assert result.is_dir()
        assert result == target

    def test_existing_directory(self, tmp_path):
        result = ensure_backup_dir(str(tmp_path))
        assert result == tmp_path


# ---------------------------------------------------------------------------
# Filename pattern
# ---------------------------------------------------------------------------


class TestBackupFilenamePattern:
    def test_valid_filename(self):
        assert BACKUP_FILENAME_PATTERN.match("codehive-2026-03-16T10-30-00.sql.gz")

    def test_invalid_filename(self):
        assert not BACKUP_FILENAME_PATTERN.match("random-file.sql.gz")
        assert not BACKUP_FILENAME_PATTERN.match("codehive-backup.tar.gz")


# ---------------------------------------------------------------------------
# Create backup (mocked subprocess)
# ---------------------------------------------------------------------------


class TestCreateBackup:
    def test_creates_backup_file(self, tmp_path):
        """pg_dump is mocked; verify file is created with correct pattern."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"-- SQL dump data"
        mock_result.stderr = b""

        with patch("codehive.core.backup.subprocess.run", return_value=mock_result):
            filepath = create_backup(
                "postgresql://user:pass@localhost:5432/testdb",
                str(tmp_path),
            )

        assert filepath.exists()
        assert BACKUP_FILENAME_PATTERN.match(filepath.name)
        # Verify it is valid gzip
        with gzip.open(filepath, "rb") as f:
            content = f.read()
        assert content == b"-- SQL dump data"

    def test_pg_dump_not_found(self, tmp_path):
        """When pg_dump is not installed, raise RuntimeError."""
        with patch(
            "codehive.core.backup.subprocess.run",
            side_effect=FileNotFoundError("pg_dump not found"),
        ):
            with pytest.raises(RuntimeError, match="pg_dump not found"):
                create_backup(
                    "postgresql://user:pass@localhost:5432/testdb",
                    str(tmp_path),
                )

    def test_pg_dump_fails(self, tmp_path):
        """When pg_dump returns non-zero, raise RuntimeError."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"connection refused"

        with patch("codehive.core.backup.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="pg_dump failed"):
                create_backup(
                    "postgresql://user:pass@localhost:5432/testdb",
                    str(tmp_path),
                )


# ---------------------------------------------------------------------------
# List backups
# ---------------------------------------------------------------------------


class TestListBackups:
    def _create_fake_backups(self, directory: Path, count: int) -> list[str]:
        """Create fake backup files with sequential timestamps."""
        names = []
        for i in range(count):
            name = f"codehive-2026-03-{10 + i:02d}T10-00-00.sql.gz"
            (directory / name).write_bytes(gzip.compress(b"data" * (i + 1)))
            names.append(name)
        return names

    def test_list_empty_directory(self, tmp_path):
        backups = list_backups(str(tmp_path))
        assert backups == []

    def test_list_nonexistent_directory(self, tmp_path):
        backups = list_backups(str(tmp_path / "nope"))
        assert backups == []

    def test_list_backups_sorted(self, tmp_path):
        self._create_fake_backups(tmp_path, 3)
        backups = list_backups(str(tmp_path))
        assert len(backups) == 3
        # Sorted oldest first
        assert backups[0]["filename"] == "codehive-2026-03-10T10-00-00.sql.gz"
        assert backups[2]["filename"] == "codehive-2026-03-12T10-00-00.sql.gz"

    def test_ignores_non_backup_files(self, tmp_path):
        """Non-codehive files are not listed."""
        (tmp_path / "random.txt").write_text("hello")
        (tmp_path / "other-2026-03-10.sql.gz").write_bytes(b"data")
        self._create_fake_backups(tmp_path, 2)
        backups = list_backups(str(tmp_path))
        assert len(backups) == 2

    def test_backup_has_correct_fields(self, tmp_path):
        self._create_fake_backups(tmp_path, 1)
        backups = list_backups(str(tmp_path))
        b = backups[0]
        assert "filename" in b
        assert "path" in b
        assert "size" in b
        assert "timestamp" in b
        assert "age_seconds" in b
        assert b["size"] > 0


# ---------------------------------------------------------------------------
# Prune backups
# ---------------------------------------------------------------------------


class TestPruneBackups:
    def _create_fake_backups(self, directory: Path, count: int) -> list[str]:
        names = []
        for i in range(count):
            name = f"codehive-2026-03-{10 + i:02d}T10-00-00.sql.gz"
            (directory / name).write_bytes(gzip.compress(b"data"))
            names.append(name)
        return names

    def test_prune_keeps_retention_count(self, tmp_path):
        self._create_fake_backups(tmp_path, 10)
        deleted = prune_backups(str(tmp_path), retention=7)
        assert len(deleted) == 3
        remaining = list_backups(str(tmp_path))
        assert len(remaining) == 7

    def test_prune_deletes_oldest(self, tmp_path):
        self._create_fake_backups(tmp_path, 10)
        deleted = prune_backups(str(tmp_path), retention=7)
        # Oldest 3 should be deleted
        assert "codehive-2026-03-10T10-00-00.sql.gz" in deleted
        assert "codehive-2026-03-11T10-00-00.sql.gz" in deleted
        assert "codehive-2026-03-12T10-00-00.sql.gz" in deleted

    def test_prune_no_delete_when_under_retention(self, tmp_path):
        self._create_fake_backups(tmp_path, 5)
        deleted = prune_backups(str(tmp_path), retention=7)
        assert deleted == []
        remaining = list_backups(str(tmp_path))
        assert len(remaining) == 5

    def test_prune_does_not_delete_non_backup_files(self, tmp_path):
        """Non-backup files should never be deleted by pruning."""
        (tmp_path / "important.txt").write_text("do not delete")
        self._create_fake_backups(tmp_path, 10)
        prune_backups(str(tmp_path), retention=7)
        assert (tmp_path / "important.txt").exists()
        assert (tmp_path / "important.txt").read_text() == "do not delete"


# ---------------------------------------------------------------------------
# Restore backup (mocked subprocess)
# ---------------------------------------------------------------------------


class TestRestoreBackup:
    def test_restore_calls_psql(self, tmp_path):
        backup_file = tmp_path / "codehive-2026-03-16T10-00-00.sql.gz"
        backup_file.write_bytes(gzip.compress(b"-- SQL dump"))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = b""

        with patch("codehive.core.backup.subprocess.run", return_value=mock_result) as mock_run:
            restore_backup(
                "postgresql://user:pass@localhost:5432/testdb",
                str(backup_file),
            )

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "psql"
        assert "-h" in cmd
        assert "localhost" in cmd

    def test_restore_file_not_found(self, tmp_path):
        with pytest.raises(RuntimeError, match="Backup file not found"):
            restore_backup(
                "postgresql://user:pass@localhost:5432/testdb",
                str(tmp_path / "nonexistent.sql.gz"),
            )

    def test_restore_psql_not_found(self, tmp_path):
        backup_file = tmp_path / "codehive-2026-03-16T10-00-00.sql.gz"
        backup_file.write_bytes(gzip.compress(b"-- SQL dump"))

        with patch(
            "codehive.core.backup.subprocess.run",
            side_effect=FileNotFoundError("psql not found"),
        ):
            with pytest.raises(RuntimeError, match="psql not found"):
                restore_backup(
                    "postgresql://user:pass@localhost:5432/testdb",
                    str(backup_file),
                )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestBackupCli:
    def _run_cli(self, args: list[str], monkeypatch) -> tuple[str, int]:
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive"] + args)
        out = StringIO()
        monkeypatch.setattr("sys.stdout", out)
        err = StringIO()
        monkeypatch.setattr("sys.stderr", err)
        try:
            main()
            return out.getvalue(), 0
        except SystemExit as e:
            return out.getvalue() + err.getvalue(), e.code or 0

    def test_backup_create_via_cli(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEHIVE_BACKUP_DIR", str(tmp_path))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"-- SQL dump"
        mock_result.stderr = b""

        with patch("codehive.core.backup.subprocess.run", return_value=mock_result):
            output, code = self._run_cli(["backup", "create"], monkeypatch)

        assert code == 0
        assert "Backup created:" in output

    def test_backup_list_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEHIVE_BACKUP_DIR", str(tmp_path))
        output, code = self._run_cli(["backup", "list"], monkeypatch)
        assert code == 0
        assert "No backups found" in output

    def test_backup_list_with_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEHIVE_BACKUP_DIR", str(tmp_path))
        # Create fake backups
        for i in range(3):
            name = f"codehive-2026-03-{10 + i:02d}T10-00-00.sql.gz"
            (tmp_path / name).write_bytes(gzip.compress(b"data"))
        output, code = self._run_cli(["backup", "list"], monkeypatch)
        assert code == 0
        assert "3 backup(s)" in output

    def test_backup_restore_with_yes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEHIVE_BACKUP_DIR", str(tmp_path))
        backup_file = tmp_path / "codehive-2026-03-16T10-00-00.sql.gz"
        backup_file.write_bytes(gzip.compress(b"-- SQL dump"))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = b""

        with patch("codehive.core.backup.subprocess.run", return_value=mock_result):
            output, code = self._run_cli(
                ["backup", "restore", str(backup_file), "--yes"],
                monkeypatch,
            )

        assert code == 0
        assert "Database restored" in output

    def test_backup_default_action_is_create(self, tmp_path, monkeypatch):
        """Running 'codehive backup' without subcommand should create a backup."""
        monkeypatch.setenv("CODEHIVE_BACKUP_DIR", str(tmp_path))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"-- SQL dump"
        mock_result.stderr = b""

        with patch("codehive.core.backup.subprocess.run", return_value=mock_result):
            output, code = self._run_cli(["backup"], monkeypatch)

        assert code == 0
        assert "Backup created:" in output


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


class TestFormatHelpers:
    def test_format_size_bytes(self):
        assert format_size(500) == "500 B"

    def test_format_size_kb(self):
        assert format_size(2048) == "2.0 KB"

    def test_format_size_mb(self):
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_format_age_seconds(self):
        assert format_age(30) == "30s ago"

    def test_format_age_minutes(self):
        assert format_age(300) == "5m ago"

    def test_format_age_hours(self):
        assert format_age(7200) == "2h ago"

    def test_format_age_days(self):
        assert format_age(172800) == "2d ago"
