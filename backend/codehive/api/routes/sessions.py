"""CRUD + state transition endpoints for sessions."""

import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.diff import DiffFileEntry, SessionDiffsResponse
from codehive.api.schemas.session import (
    MessageSend,
    ModeSwitchRequest,
    SessionCreate,
    SessionRead,
    SessionUpdate,
)
from codehive.execution.diff import DiffService
from codehive.core.session import (
    InvalidStatusTransitionError,
    IssueNotFoundError,
    NoUserMessageError,
    ProjectNotFoundError,
    SessionHasDependentsError,
    SessionNotFoundError,
    create_session,
    delete_session,
    get_session,
    list_child_sessions,
    list_sessions,
    pause_session,
    resume_interrupted_session,
    resume_session,
    update_session,
)

# Project-scoped routes (create, list)
project_sessions_router = APIRouter(prefix="/api/projects/{project_id}/sessions", tags=["sessions"])

# Flat routes (get, update, delete, pause, resume)
sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _get_session_or_404(
    db: AsyncSession,
    session_id: uuid.UUID,
):
    """Get session or raise 404."""
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@project_sessions_router.post("", response_model=SessionRead, status_code=201)
async def create_session_endpoint(
    project_id: uuid.UUID,
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    try:
        session = await create_session(
            db,
            project_id=project_id,
            name=body.name,
            engine=body.engine,
            mode=body.mode,
            issue_id=body.issue_id,
            parent_session_id=body.parent_session_id,
            config=body.config,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Parent session not found")
    return SessionRead.model_validate(session)


@project_sessions_router.get("", response_model=list[SessionRead])
async def list_sessions_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SessionRead]:
    try:
        sessions = await list_sessions(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return [SessionRead.model_validate(s) for s in sessions]


@sessions_router.get("/{session_id}", response_model=SessionRead)
async def get_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    session = await _get_session_or_404(db, session_id)
    return SessionRead.model_validate(session)


@sessions_router.patch("/{session_id}", response_model=SessionRead)
async def update_session_endpoint(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    session = await _get_session_or_404(db, session_id)
    fields = body.model_dump(exclude_unset=True)
    try:
        session = await update_session(db, session_id, **fields)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


@sessions_router.delete("/{session_id}", status_code=204)
async def delete_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_session_or_404(db, session_id)
    try:
        await delete_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionHasDependentsError:
        raise HTTPException(
            status_code=409,
            detail="Session has child sessions",
        )


@sessions_router.post("/{session_id}/pause", response_model=SessionRead)
async def pause_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    session = await _get_session_or_404(db, session_id)
    try:
        session = await pause_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SessionRead.model_validate(session)


@sessions_router.post("/{session_id}/resume", response_model=SessionRead)
async def resume_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    session = await _get_session_or_404(db, session_id)
    try:
        session = await resume_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SessionRead.model_validate(session)


@sessions_router.post("/{session_id}/resume-interrupted", response_model=SessionRead)
async def resume_interrupted_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    """Resume an interrupted session by replaying the last user message."""
    await _get_session_or_404(db, session_id)
    try:
        session, _last_message = await resume_interrupted_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NoUserMessageError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SessionRead.model_validate(session)


@sessions_router.post("/{session_id}/switch-mode", response_model=SessionRead)
async def switch_mode_endpoint(
    session_id: uuid.UUID,
    body: ModeSwitchRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    """Switch a session's mode."""
    session = await _get_session_or_404(db, session_id)
    try:
        session = await update_session(db, session_id, mode=body.mode)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


@sessions_router.get("/{session_id}/subagents", response_model=list[SessionRead])
async def list_subagents_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SessionRead]:
    """Return the list of child sessions (sub-agents) for a session."""
    await _get_session_or_404(db, session_id)
    try:
        children = await list_child_sessions(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return [SessionRead.model_validate(c) for c in children]


def _count_additions_deletions(diff_text: str) -> tuple[int, int]:
    """Count addition and deletion lines in a unified diff text."""
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return additions, deletions


# Module-level shared DiffService instance.
_diff_service = DiffService()


def get_diff_service() -> DiffService:
    """Return the shared DiffService singleton."""
    return _diff_service


@sessions_router.get("/{session_id}/diffs", response_model=SessionDiffsResponse)
async def get_session_diffs_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    diff_service: DiffService = Depends(get_diff_service),
) -> SessionDiffsResponse:
    """Return all tracked file diffs for a session."""
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    changes = diff_service.get_session_changes(str(session_id))
    files: list[DiffFileEntry] = []
    for path, diff_text in changes.items():
        additions, deletions = _count_additions_deletions(diff_text)
        files.append(
            DiffFileEntry(
                path=path,
                diff_text=diff_text,
                additions=additions,
                deletions=deletions,
            )
        )
    return SessionDiffsResponse(session_id=str(session_id), files=files)


class AgentMessageRequest(BaseModel):
    """Request body for inter-agent messaging."""

    target_session_id: uuid.UUID
    message: str


@sessions_router.post("/{session_id}/messages/agent")
async def send_agent_message_endpoint(
    session_id: uuid.UUID,
    body: AgentMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a message from one agent to another.

    Creates agent.message events on both session event streams.
    """
    from codehive.core.agent_comm import AgentCommService

    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    target = await get_session(db, body.target_session_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target session not found")

    # Use AgentCommService without event bus (no Redis needed for API call)
    comm = AgentCommService()
    result = await comm.send_to_agent(
        db,
        sender_session_id=session_id,
        target_session_id=body.target_session_id,
        message=body.message,
    )
    return result


async def _build_engine(session_config: dict, engine_type: str = "native") -> Any:
    """Construct an engine adapter based on the engine type.

    Returns a NativeEngine for ``"native"`` and a ClaudeCodeEngine for
    ``"claude_code"``.  Raises 400 for unknown engine types.

    Separated into a helper so tests can override it easily.
    """
    from pathlib import Path

    from codehive.execution.diff import DiffService

    project_root = Path(session_config.get("project_root", "/tmp"))
    diff_service = DiffService()

    if engine_type == "claude_code":
        from codehive.engine.claude_code_engine import ClaudeCodeEngine

        return ClaudeCodeEngine(
            diff_service=diff_service,
            working_dir=str(project_root),
        )

    if engine_type == "native":
        from anthropic import AsyncAnthropic

        from codehive.config import Settings
        from codehive.core.events import EventBus
        from codehive.engine.native import NativeEngine
        from codehive.execution.file_ops import FileOps
        from codehive.execution.git_ops import GitOps
        from codehive.execution.shell import ShellRunner

        settings = Settings()
        if not settings.anthropic_api_key:
            raise HTTPException(status_code=503, detail="Engine not configured")

        client_kwargs: dict[str, Any] = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            client_kwargs["base_url"] = settings.anthropic_base_url
        client = AsyncAnthropic(**client_kwargs)
        redis_client: Any = None
        try:
            from redis.asyncio import Redis

            redis_client = Redis.from_url(settings.redis_url)
        except Exception:
            pass

        event_bus = EventBus(redis_client) if redis_client else None  # type: ignore[arg-type]
        file_ops = FileOps(project_root=project_root)
        shell_runner = ShellRunner()
        git_ops = GitOps(repo_path=project_root)

        model = session_config.get("model", "") or settings.default_model

        return NativeEngine(
            client=client,
            event_bus=event_bus,  # type: ignore[arg-type]
            file_ops=file_ops,
            shell_runner=shell_runner,
            git_ops=git_ops,
            diff_service=diff_service,
            model=model,
        )

    raise HTTPException(status_code=400, detail=f"Unknown engine type: {engine_type}")


@sessions_router.post("/{session_id}/messages")
async def send_message_endpoint(
    session_id: uuid.UUID,
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Send a message to a session and return engine events as a batch."""
    # Verify session exists
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Mark session as executing
    try:
        await update_session(db, session_id, status="executing")
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        engine = await _build_engine(session.config, engine_type=session.engine)

        events: list[dict[str, Any]] = []
        async for event in engine.send_message(session_id, body.content, db=db):
            events.append(event)

        # Engine finished a turn -- mark as waiting_input
        await update_session(db, session_id, status="waiting_input")

        return events
    except HTTPException:
        # On HTTP errors, mark as failed
        try:
            await update_session(db, session_id, status="failed")
        except Exception:
            pass
        raise
    except Exception as exc:
        # On unexpected errors, mark as failed
        try:
            await update_session(db, session_id, status="failed")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc))


@sessions_router.post("/{session_id}/messages/stream")
async def send_message_stream_endpoint(
    session_id: uuid.UUID,
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Send a message to a session and stream engine events as SSE.

    Returns a ``text/event-stream`` response where each event is a
    JSON-encoded ``data:`` line.  The stream ends when the engine turn
    completes.
    """
    # Verify session exists
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Mark session as executing
    try:
        await update_session(db, session_id, status="executing")
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    async def _event_generator() -> AsyncIterator[str]:
        try:
            engine = await _build_engine(session.config, engine_type=session.engine)

            async for event in engine.send_message(session_id, body.content, db=db):
                yield f"data: {json.dumps(event)}\n\n"

            # Engine finished a turn -- mark as waiting_input
            await update_session(db, session_id, status="waiting_input")
        except Exception as exc:
            # On errors, mark as failed and send error event
            try:
                await update_session(db, session_id, status="failed")
            except Exception:
                pass
            error_event = {
                "type": "error",
                "content": str(exc),
                "session_id": str(session_id),
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
