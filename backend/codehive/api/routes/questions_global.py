"""Cross-session question endpoints: list all questions, get single question."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.question import QuestionRead
from codehive.core.pending_questions import get_question
from codehive.db.models import PendingQuestion

global_questions_router = APIRouter(prefix="/api/questions", tags=["questions"])


@global_questions_router.get("", response_model=list[QuestionRead])
async def list_all_questions(
    answered: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionRead]:
    """List questions across all sessions, with optional answered filter."""
    stmt = select(PendingQuestion).order_by(PendingQuestion.created_at.asc())
    if answered is not None:
        stmt = stmt.where(PendingQuestion.answered == answered)
    result = await db.execute(stmt)
    questions = list(result.scalars().all())
    return [QuestionRead.model_validate(q) for q in questions]


@global_questions_router.get("/{question_id}", response_model=QuestionRead)
async def get_question_by_id(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> QuestionRead:
    """Get a single question by ID."""
    pq = await get_question(db, question_id)
    if pq is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionRead.model_validate(pq)
