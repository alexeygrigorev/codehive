"""System endpoints: extended health check and maintenance mode."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.__version__ import __version__
from codehive.api.deps import get_db
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
