"""Usage tracking API routes."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.usage import estimate_cost, get_context_usage
from codehive.db.models import ModelUsageSnapshot, RateLimitSnapshot
from codehive.db.models import Session as SessionModel
from codehive.db.models import UsageRecord

usage_router = APIRouter(prefix="/api/usage", tags=["usage"])
session_usage_router = APIRouter(prefix="/api/sessions", tags=["usage"])


class UsageRecordRead(BaseModel):
    id: str
    session_id: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    created_at: str

    model_config = {"from_attributes": True}


class UsageSummary(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost: float


class UsageResponse(BaseModel):
    records: list[UsageRecordRead]
    summary: UsageSummary


def _parse_date(d: date | None) -> datetime | None:
    if d is None:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _build_usage_query(
    session_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Build a base query for usage records with optional filters."""
    query = select(UsageRecord)

    if session_id is not None:
        query = query.where(UsageRecord.session_id == session_id)

    if project_id is not None:
        query = query.join(SessionModel, UsageRecord.session_id == SessionModel.id).where(
            SessionModel.project_id == project_id
        )

    if start_date is not None:
        start_dt = _parse_date(start_date)
        query = query.where(UsageRecord.created_at >= start_dt)

    if end_date is not None:
        # End date is inclusive, so go to the next day
        end_dt = datetime(
            end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc
        )
        query = query.where(UsageRecord.created_at <= end_dt)

    return query


def _record_to_read(record: UsageRecord) -> UsageRecordRead:
    cost = estimate_cost(record.model, record.input_tokens, record.output_tokens)
    return UsageRecordRead(
        id=str(record.id),
        session_id=str(record.session_id),
        model=record.model,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        estimated_cost=cost,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


def _compute_summary(records: list[UsageRecordRead]) -> UsageSummary:
    total_input = sum(r.input_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_cost = sum(r.estimated_cost for r in records)
    return UsageSummary(
        total_requests=len(records),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        estimated_cost=round(total_cost, 6),
    )


@usage_router.get("", response_model=UsageResponse)
async def get_usage(
    session_id: uuid.UUID | None = Query(None),
    project_id: uuid.UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Query usage records with optional filters."""
    query = _build_usage_query(session_id, project_id, start_date, end_date)
    query = query.order_by(UsageRecord.created_at.desc())
    result = await db.execute(query)
    rows = result.scalars().all()
    records = [_record_to_read(r) for r in rows]
    summary = _compute_summary(records)
    return UsageResponse(records=records, summary=summary)


@usage_router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    session_id: uuid.UUID | None = Query(None),
    project_id: uuid.UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    """Get aggregated usage summary."""
    query = _build_usage_query(session_id, project_id, start_date, end_date)
    result = await db.execute(query)
    rows = result.scalars().all()
    records = [_record_to_read(r) for r in rows]
    return _compute_summary(records)


class ContextUsageResponse(BaseModel):
    used_tokens: int
    context_window: int
    usage_percent: float
    model: str
    estimated: bool = False


@session_usage_router.get("/{session_id}/context", response_model=ContextUsageResponse)
async def get_session_context(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ContextUsageResponse:
    """Get context window usage for a specific session."""
    data = await get_context_usage(db, session_id)
    return ContextUsageResponse(**data)  # type: ignore[arg-type]


@session_usage_router.get("/{session_id}/usage", response_model=UsageSummary)
async def get_session_usage(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    """Get usage summary for a specific session."""
    query = select(UsageRecord).where(UsageRecord.session_id == session_id)
    result = await db.execute(query)
    rows = result.scalars().all()
    records = [_record_to_read(r) for r in rows]
    return _compute_summary(records)


# ---------------------------------------------------------------------------
# Plan limits & per-model breakdown
# ---------------------------------------------------------------------------


class RateLimitRead(BaseModel):
    rate_limit_type: str
    utilization: float
    resets_at: int
    is_using_overage: bool
    surpassed_threshold: float | None = None
    captured_at: str


class ModelUsageRead(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_usd: float
    context_window: int | None = None
    captured_at: str


class UsageLimitsResponse(BaseModel):
    rate_limits: list[RateLimitRead]
    model_usage: list[ModelUsageRead]


@usage_router.get("/limits", response_model=UsageLimitsResponse)
async def get_usage_limits(
    db: AsyncSession = Depends(get_db),
) -> UsageLimitsResponse:
    """Return latest rate limit snapshots and per-model usage breakdown."""
    # Get the latest snapshot per rate_limit_type using a subquery
    from sqlalchemy import func

    # Latest rate limit per type
    subq = (
        select(
            RateLimitSnapshot.rate_limit_type,
            func.max(RateLimitSnapshot.captured_at).label("max_captured"),
        )
        .group_by(RateLimitSnapshot.rate_limit_type)
        .subquery()
    )
    rl_query = select(RateLimitSnapshot).join(
        subq,
        (RateLimitSnapshot.rate_limit_type == subq.c.rate_limit_type)
        & (RateLimitSnapshot.captured_at == subq.c.max_captured),
    )
    rl_result = await db.execute(rl_query)
    rl_rows = rl_result.scalars().all()

    rate_limits = [
        RateLimitRead(
            rate_limit_type=r.rate_limit_type,
            utilization=r.utilization,
            resets_at=r.resets_at,
            is_using_overage=r.is_using_overage,
            surpassed_threshold=r.surpassed_threshold,
            captured_at=r.captured_at.isoformat() if r.captured_at else "",
        )
        for r in rl_rows
    ]

    # Get per-model usage from the most recent batch (same captured_at)
    latest_mu = (select(func.max(ModelUsageSnapshot.captured_at).label("max_captured"))).subquery()
    mu_query = select(ModelUsageSnapshot).where(
        ModelUsageSnapshot.captured_at == select(latest_mu.c.max_captured).scalar_subquery()
    )
    mu_result = await db.execute(mu_query)
    mu_rows = mu_result.scalars().all()

    model_usage = [
        ModelUsageRead(
            model=m.model,
            input_tokens=m.input_tokens,
            output_tokens=m.output_tokens,
            cache_read_tokens=m.cache_read_tokens,
            cache_creation_tokens=m.cache_creation_tokens,
            cost_usd=m.cost_usd,
            context_window=m.context_window,
            captured_at=m.captured_at.isoformat() if m.captured_at else "",
        )
        for m in mu_rows
    ]

    return UsageLimitsResponse(rate_limits=rate_limits, model_usage=model_usage)
