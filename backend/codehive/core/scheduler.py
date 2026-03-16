"""Session scheduler: auto-next task pickup and pending question management."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import EventBus
from codehive.core.pending_questions import create_question, list_questions
from codehive.core.task_queue import get_next_task, transition_task
from codehive.db.models import Issue
from codehive.db.models import Session as SessionModel


class EngineAdapter(Protocol):
    """Minimal protocol for the engine adapter used by the scheduler."""

    async def start_task(
        self,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        *,
        db: Any = None,
        task_instructions: str | None = None,
    ) -> Any: ...

    async def send_message(
        self,
        session_id: uuid.UUID,
        message: str,
        **kwargs: Any,
    ) -> AsyncIterator[dict]: ...


class SessionScheduler:
    """Connects the engine to the task queue with auto-next and pending questions."""

    def __init__(
        self,
        db_session_factory: Any,
        event_bus: EventBus,
        engine: EngineAdapter,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._event_bus = event_bus
        self._engine = engine

    async def on_task_completed(
        self,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        *,
        db: AsyncSession,
    ) -> None:
        """Handle a task completion: emit event, then auto-pick the next task if enabled."""
        # Emit task.completed event
        await self._event_bus.publish(
            db,
            session_id,
            "task.completed",
            {"task_id": str(task_id)},
        )

        # Check session config for queue_enabled
        session = await db.get(SessionModel, session_id)
        if session is None:
            return

        config = session.config or {}
        queue_enabled = config.get("queue_enabled", True)

        if not queue_enabled:
            # No auto-pickup; transition to idle
            session.status = "idle"
            await db.commit()
            await db.refresh(session)
            await self._event_bus.publish(
                db,
                session_id,
                "session.status_changed",
                {"status": "idle"},
            )
            return

        # Try to get the next actionable task
        next_task = await get_next_task(db, session_id)

        if next_task is not None:
            # Transition task to running
            await transition_task(db, next_task.id, "running")

            # Set session to executing
            session.status = "executing"
            await db.commit()
            await db.refresh(session)

            # Emit events
            await self._event_bus.publish(
                db,
                session_id,
                "task.started",
                {"task_id": str(next_task.id)},
            )
            await self._event_bus.publish(
                db,
                session_id,
                "session.status_changed",
                {"status": "executing"},
            )

            # Start the task on the engine
            await self._engine.start_task(session_id, next_task.id, db=db)
        else:
            # No tasks remaining; dispatch on queue_empty_action
            action = config.get("queue_empty_action", "stop")
            await self._handle_queue_empty(session, action, db=db)

    async def _handle_queue_empty(
        self,
        session: SessionModel,
        action: str,
        *,
        db: AsyncSession,
    ) -> None:
        """Dispatch on queue_empty_action when the task queue is empty."""
        session_id = session.id

        if action == "ask":
            # Create a pending question and transition to waiting_input
            pq = await create_question(
                db,
                session_id,
                "All tasks are complete. Should I continue generating new tasks or stop?",
            )
            session.status = "waiting_input"
            await db.commit()
            await db.refresh(session)
            await self._event_bus.publish(
                db,
                session_id,
                "queue_empty.ask",
                {"question_id": str(pq.id)},
            )
            await self._event_bus.publish(
                db,
                session_id,
                "session.status_changed",
                {"status": "waiting_input"},
            )

        elif action == "continue":
            # Try to generate new tasks from the linked issue
            issue_id = session.issue_id
            if issue_id is None:
                # No linked issue; fall back to stop
                await self._transition_to_idle(session, db=db)
                return

            issue = await db.get(Issue, issue_id)
            if issue is None:
                await self._transition_to_idle(session, db=db)
                return

            # Emit event before calling the engine
            await self._event_bus.publish(
                db,
                session_id,
                "queue_empty.continue",
                {"issue_id": str(issue_id)},
            )

            # Ask the engine to generate new tasks
            prompt = (
                f"All tasks are complete for issue: {issue.title}\n\n"
                f"Description: {issue.description or 'No description provided.'}\n\n"
                f"Please analyze the issue and create new tasks if more work is needed."
            )
            async for _event in self._engine.send_message(session_id, prompt, db=db):
                pass  # consume the stream

            # Check if new tasks were generated
            next_task = await get_next_task(db, session_id)
            if next_task is not None:
                await transition_task(db, next_task.id, "running")
                session.status = "executing"
                await db.commit()
                await db.refresh(session)
                await self._event_bus.publish(
                    db,
                    session_id,
                    "task.started",
                    {"task_id": str(next_task.id)},
                )
                await self._event_bus.publish(
                    db,
                    session_id,
                    "session.status_changed",
                    {"status": "executing"},
                )
                await self._engine.start_task(session_id, next_task.id, db=db)
            else:
                await self._transition_to_idle(session, db=db)

        else:
            # Default: "stop" -- transition to idle
            await self._transition_to_idle(session, db=db)

    async def _transition_to_idle(
        self,
        session: SessionModel,
        *,
        db: AsyncSession,
    ) -> None:
        """Set session to idle and emit status change event."""
        session.status = "idle"
        await db.commit()
        await db.refresh(session)
        await self._event_bus.publish(
            db,
            session.id,
            "session.status_changed",
            {"status": "idle"},
        )

    async def on_question_asked(
        self,
        session_id: uuid.UUID,
        question_text: str,
        context: str | None = None,
        *,
        db: AsyncSession,
    ) -> None:
        """Handle a question from the engine: create a PendingQuestion, then decide next action."""
        # Create the pending question record
        pq = await create_question(db, session_id, question_text, context)

        # Emit question.asked event
        await self._event_bus.publish(
            db,
            session_id,
            "question.asked",
            {
                "question_id": str(pq.id),
                "question": question_text,
                "context": context,
            },
        )

        # Check if there are remaining tasks in the queue
        next_task = await get_next_task(db, session_id)

        session = await db.get(SessionModel, session_id)
        if session is None:
            return

        if next_task is not None:
            # Defer the question, auto-start the next task
            await transition_task(db, next_task.id, "running")

            session.status = "executing"
            await db.commit()
            await db.refresh(session)

            await self._event_bus.publish(
                db,
                session_id,
                "task.started",
                {"task_id": str(next_task.id)},
            )
            await self._event_bus.publish(
                db,
                session_id,
                "session.status_changed",
                {"status": "executing"},
            )

            await self._engine.start_task(session_id, next_task.id, db=db)
        else:
            # No tasks remaining; transition to waiting_input
            session.status = "waiting_input"
            await db.commit()
            await db.refresh(session)

            await self._event_bus.publish(
                db,
                session_id,
                "session.status_changed",
                {"status": "waiting_input"},
            )

    async def on_question_answered(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        *,
        db: AsyncSession,
    ) -> None:
        """Handle a question being answered: emit event, check if session should transition."""
        # Emit question.answered event
        from codehive.core.pending_questions import get_question

        pq = await get_question(db, question_id)
        answer_text = pq.answer if pq else None

        await self._event_bus.publish(
            db,
            session_id,
            "question.answered",
            {
                "question_id": str(question_id),
                "answer": answer_text,
            },
        )

        # Check if the session was waiting_input and all questions are now answered
        session = await db.get(SessionModel, session_id)
        if session is None:
            return

        if session.status == "waiting_input":
            unanswered = await list_questions(db, session_id, answered=False)
            if len(unanswered) == 0:
                session.status = "idle"
                await db.commit()
                await db.refresh(session)
                await self._event_bus.publish(
                    db,
                    session_id,
                    "session.status_changed",
                    {"status": "idle"},
                )
