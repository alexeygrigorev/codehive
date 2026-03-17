"""CRUD operations for PendingQuestion model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import PendingQuestion
from codehive.db.models import Session as SessionModel


class SessionNotFoundError(Exception):
    """Raised when a session_id does not exist."""


class QuestionNotFoundError(Exception):
    """Raised when a question is not found by ID."""


class QuestionAlreadyAnsweredError(Exception):
    """Raised when attempting to answer an already-answered question."""


async def _verify_session_exists(db: AsyncSession, session_id: uuid.UUID) -> None:
    """Raise SessionNotFoundError if session does not exist."""
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")


async def create_question(
    db: AsyncSession,
    session_id: uuid.UUID,
    question: str,
    context: str | None = None,
) -> PendingQuestion:
    """Create a new pending question for a session."""
    await _verify_session_exists(db, session_id)

    pq = PendingQuestion(
        session_id=session_id,
        question=question,
        context=context,
        answered=False,
        answer=None,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(pq)
    await db.commit()
    await db.refresh(pq)
    return pq


async def list_questions(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    answered: bool | None = None,
) -> list[PendingQuestion]:
    """Return pending questions for a session, ordered by created_at ascending.

    If answered is None, return all. If True/False, filter accordingly.
    """
    await _verify_session_exists(db, session_id)

    stmt = (
        select(PendingQuestion)
        .where(PendingQuestion.session_id == session_id)
        .order_by(PendingQuestion.created_at.asc())
    )
    if answered is not None:
        stmt = stmt.where(PendingQuestion.answered == answered)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_question(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> PendingQuestion | None:
    """Return a question by ID, or None if not found."""
    return await db.get(PendingQuestion, question_id)


async def answer_question(
    db: AsyncSession,
    question_id: uuid.UUID,
    answer: str,
) -> PendingQuestion:
    """Answer a pending question. Raises error if already answered or not found."""
    pq = await db.get(PendingQuestion, question_id)
    if pq is None:
        raise QuestionNotFoundError(f"Question {question_id} not found")
    if pq.answered:
        raise QuestionAlreadyAnsweredError(f"Question {question_id} is already answered")

    pq.answered = True
    pq.answer = answer
    await db.commit()
    await db.refresh(pq)
    return pq
