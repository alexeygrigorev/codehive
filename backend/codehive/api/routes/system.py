"""System endpoints: extended health check, maintenance mode, directory browsing."""

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.__version__ import __version__
from codehive.api.deps import get_db
from codehive.config import Settings
from codehive.db.models import Session as SessionModel

system_router = APIRouter(prefix="/api/system", tags=["system"])


class HealthResponse(BaseModel):
    version: str
    database: str
    redis: str
    active_sessions: int
    maintenance: bool


class MaintenanceRequest(BaseModel):
    enabled: bool


class MaintenanceResponse(BaseModel):
    maintenance: bool


@system_router.get("/health", response_model=HealthResponse)
async def system_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Extended health check with database, redis, active sessions, maintenance."""
    # Database check
    db_status = "connected"
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Redis check
    redis_status = "disconnected"
    try:
        from redis.asyncio import Redis
        from codehive.config import Settings

        settings = Settings()
        r = Redis.from_url(settings.redis_url)
        await r.ping()
        redis_status = "connected"
        await r.aclose()
    except Exception:
        redis_status = "disconnected"

    # Active sessions count
    active_sessions = 0
    try:
        stmt = (
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.status.in_(["executing", "planning"]))
        )
        result = await db.execute(stmt)
        active_sessions = result.scalar() or 0
    except Exception:
        pass

    # Maintenance flag
    maintenance = getattr(request.app.state, "maintenance", False)

    return HealthResponse(
        version=__version__,
        database=db_status,
        redis=redis_status,
        active_sessions=active_sessions,
        maintenance=maintenance,
    )


@system_router.post("/maintenance", response_model=MaintenanceResponse)
async def set_maintenance(
    request: Request,
    body: MaintenanceRequest,
) -> MaintenanceResponse:
    """Toggle maintenance mode."""
    request.app.state.maintenance = body.enabled
    return MaintenanceResponse(maintenance=body.enabled)


# ---------------------------------------------------------------------------
# Default directory & directory browser
# ---------------------------------------------------------------------------


class DefaultDirectoryResponse(BaseModel):
    default_directory: str


class DirectoryEntry(BaseModel):
    name: str
    path: str
    has_git: bool


class DirectoryListResponse(BaseModel):
    path: str
    parent: str | None
    directories: list[DirectoryEntry]


def _resolve_projects_dir() -> str:
    """Return the resolved absolute projects directory from settings."""
    settings = Settings()
    return os.path.normpath(os.path.expanduser(settings.projects_dir))


def _is_within_home(path: str) -> bool:
    """Check whether *path* is within the user's home directory."""
    home = os.path.expanduser("~")
    # Normalize to avoid traversal tricks
    normalized = os.path.normpath(os.path.realpath(path))
    return normalized == home or normalized.startswith(home + os.sep)


@system_router.get("/default-directory", response_model=DefaultDirectoryResponse)
async def default_directory() -> DefaultDirectoryResponse:
    """Return the configured default base directory for new projects."""
    resolved = _resolve_projects_dir()
    # Ensure trailing slash so the user can just append a project name
    return DefaultDirectoryResponse(default_directory=resolved + "/")


@system_router.get("/directories", response_model=DirectoryListResponse)
async def list_directories(
    path: str = Query(..., description="Absolute directory path to list"),
) -> DirectoryListResponse:
    """List subdirectories at the given path.

    Security: the path must be within the user's home directory.
    Hidden directories (starting with ``"."``) are excluded from the listing.
    """
    normalized = os.path.normpath(os.path.expanduser(path))

    if not _is_within_home(normalized):
        raise HTTPException(status_code=403, detail="Path is outside the home directory")

    if not os.path.isdir(normalized):
        raise HTTPException(status_code=404, detail="Directory not found")

    entries: list[DirectoryEntry] = []
    try:
        with os.scandir(normalized) as it:
            for entry in sorted(it, key=lambda e: e.name.lower()):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name.startswith("."):
                    continue
                # Check symlink doesn't escape home
                entry_real = os.path.realpath(entry.path)
                if not _is_within_home(entry_real):
                    continue
                has_git = os.path.isdir(os.path.join(entry.path, ".git"))
                entries.append(
                    DirectoryEntry(
                        name=entry.name,
                        path=os.path.normpath(entry.path),
                        has_git=has_git,
                    )
                )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    parent = os.path.dirname(normalized)
    parent_val: str | None = parent if _is_within_home(parent) else None

    return DirectoryListResponse(
        path=normalized,
        parent=parent_val,
        directories=entries,
    )
