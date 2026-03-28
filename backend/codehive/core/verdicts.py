"""Structured verdict events for agent result reporting.

Agents submit typed verdict events instead of relying on free-text parsing.
The orchestrator reads these events programmatically from the DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Event


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class VerdictValue(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class EvidenceItem(BaseModel):
    """A single piece of evidence attached to a verdict."""

    type: str
    content: str | None = None
    path: str | None = None

    @field_validator("type")
    @classmethod
    def type_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Evidence type must not be empty")
        return v


class CriterionResult(BaseModel):
    """Per-criterion PASS/FAIL result."""

    criterion: str
    result: str
    detail: str | None = None

    @field_validator("criterion")
    @classmethod
    def criterion_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Criterion must not be empty")
        return v


class VerdictPayload(BaseModel):
    """Full verdict payload submitted by an agent."""

    verdict: VerdictValue
    role: str
    task_id: str | None = None
    evidence: list[EvidenceItem] | None = None
    criteria_results: list[CriterionResult] | None = None
    feedback: str | None = None


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------


async def submit_verdict(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    verdict: str,
    role: str,
    task_id: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    criteria_results: list[dict[str, Any]] | None = None,
    feedback: str | None = None,
) -> Event:
    """Validate inputs, create an Event with type='verdict', and return it.

    Raises ValueError if the verdict value is invalid.
    Raises ValueError if the session_id does not exist.
    """
    # Validate via Pydantic
    payload = VerdictPayload(
        verdict=verdict,  # type: ignore[arg-type]
        role=role,
        task_id=task_id,
        evidence=[EvidenceItem(**e) for e in evidence] if evidence else None,
        criteria_results=[CriterionResult(**c) for c in criteria_results]
        if criteria_results
        else None,
        feedback=feedback,
    )

    # Validate session exists
    from codehive.db.models import Session as SessionModel

    session = await db.get(SessionModel, session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")

    data = payload.model_dump(mode="json", exclude_none=True)

    event = Event(
        session_id=session_id,
        type="verdict",
        data=data,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_verdict(db: AsyncSession, session_id: uuid.UUID) -> dict[str, Any] | None:
    """Retrieve the most recent verdict event for a session.

    Returns the event's ``data`` dict, or ``None`` if no verdict event exists.
    """
    stmt = (
        select(Event)
        .where(Event.session_id == session_id, Event.type == "verdict")
        .order_by(Event.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if event is None:
        return None
    return event.data
