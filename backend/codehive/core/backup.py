"""Database backup and restore utilities using pg_dump/pg_restore."""

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BACKUP_FILENAME_PATTERN = re.compile(r"^codehive-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.sql\.gz$")


def parse_database_url(database_url: str) -> dict[str, str]:
    """Parse a DATABASE_URL into components for pg_dump/pg_restore.

    Handles both ``postgresql+asyncpg://`` (SQLAlchemy) and plain
    ``postgresql://`` schemes.
    """
    # Strip SQLAlchemy driver suffix so urlparse works cleanly
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "codehive",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/") or "codehive",
    }


def _build_env(password: str) -> dict[str, str]:
    """Return an environment dict with PGPASSWORD set."""
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    return env


def ensure_backup_dir(backup_dir: str) -> Path:
    """Create the backup directory if it does not exist and return its Path."""
    path = Path(backup_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(database_url: str, backup_dir: str) -> Path:
    """Run pg_dump and save a gzipped SQL dump.

    Returns the path to the created backup file.
    Raises ``RuntimeError`` on failure.
    """
    db = parse_database_url(database_url)
    dir_path = ensure_backup_dir(backup_dir)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"codehive-{timestamp}.sql.gz"
    filepath = dir_path / filename

    cmd = [
        "pg_dump",
        "-h",
        db["host"],
        "-p",
        db["port"],
        "-U",
        db["user"],
        "-d",
        db["dbname"],
        "--no-password",
    ]

    env = _build_env(db["password"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("pg_dump not found. Install PostgreSQL client tools.")

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}): {stderr}")

    # Compress and write
    import gzip

    with gzip.open(filepath, "wb") as f:
        f.write(result.stdout)

    return filepath


def list_backups(backup_dir: str) -> list[dict[str, str | int]]:
    """List backup files in the directory, sorted oldest-first.

    Returns a list of dicts with keys: filename, path, size, timestamp, age.
    """
    dir_path = Path(backup_dir)
    if not dir_path.is_dir():
        return []

    backups = []
    now = datetime.now(timezone.utc)
    for entry in sorted(dir_path.iterdir()):
        match = BACKUP_FILENAME_PATTERN.match(entry.name)
        if not match:
            continue
        ts_str = match.group(1)
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%dT%H-%M-%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        age = now - ts
        size = entry.stat().st_size
        backups.append(
            {
                "filename": entry.name,
                "path": str(entry),
                "size": size,
                "timestamp": ts_str,
                "age_seconds": int(age.total_seconds()),
            }
        )

    # Sort by timestamp (oldest first)
    backups.sort(key=lambda b: b["timestamp"])
    return backups


def prune_backups(backup_dir: str, retention: int) -> list[str]:
    """Delete old backups exceeding the retention count.

    Keeps the *newest* ``retention`` backups (sorted by filename timestamp).
    Returns a list of deleted filenames.
    """
    backups = list_backups(backup_dir)
    if len(backups) <= retention:
        return []

    # backups are sorted oldest-first, so delete from the front
    to_delete = backups[: len(backups) - retention]
    deleted = []
    for b in to_delete:
        Path(b["path"]).unlink()
        deleted.append(b["filename"])
    return deleted


def restore_backup(database_url: str, backup_file: str) -> None:
    """Restore a database from a gzipped SQL dump.

    Raises ``RuntimeError`` on failure.
    """
    filepath = Path(backup_file)
    if not filepath.is_file():
        raise RuntimeError(f"Backup file not found: {backup_file}")

    db = parse_database_url(database_url)
    env = _build_env(db["password"])

    import gzip

    # Decompress and pipe to psql
    with gzip.open(filepath, "rb") as f:
        sql_data = f.read()

    cmd = [
        "psql",
        "-h",
        db["host"],
        "-p",
        db["port"],
        "-U",
        db["user"],
        "-d",
        db["dbname"],
        "--no-password",
        "-q",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=sql_data,
            capture_output=True,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("psql not found. Install PostgreSQL client tools.")

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"psql restore failed (exit {result.returncode}): {stderr}")


def format_size(size_bytes: int) -> str:
    """Format a file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_age(age_seconds: int) -> str:
    """Format an age in seconds to a human-readable string."""
    if age_seconds < 60:
        return f"{age_seconds}s ago"
    elif age_seconds < 3600:
        return f"{age_seconds // 60}m ago"
    elif age_seconds < 86400:
        return f"{age_seconds // 3600}h ago"
    else:
        return f"{age_seconds // 86400}d ago"
