"""API endpoints for pending questions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.question import QuestionAnswer, QuestionRead
from codehive.core.pending_questions import (
    QuestionAlreadyAnsweredError,
    QuestionNotFoundError,
    SessionNotFoundError,
    answer_question,
    get_question,
    list_questions,
)

questions_router = APIRouter(
    prefix="/api/sessions/{session_id}/questions",
    tags=["questions"],
)


@questions_router.get("", response_model=list[QuestionRead])
async def list_questions_endpoint(
    session_id: uuid.UUID,
    answered: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionRead]:
    try:
        questions = await list_questions(db, session_id, answered=answered)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return [QuestionRead.model_validate(q) for q in questions]


@questions_router.post(
    "/{question_id}/answer",
    response_model=QuestionRead,
)
async def answer_question_endpoint(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    body: QuestionAnswer,
    db: AsyncSession = Depends(get_db),
) -> QuestionRead:
    # Verify the question belongs to this session
    pq = await get_question(db, question_id)
    if pq is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if pq.session_id != session_id:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        updated = await answer_question(db, question_id, body.answer)
    except QuestionNotFoundError:
        raise HTTPException(status_code=404, detail="Question not found")
    except QuestionAlreadyAnsweredError:
        raise HTTPException(status_code=409, detail="Question already answered")
    return QuestionRead.model_validate(updated)
