"""Search service with SQLite LIKE fallback and PostgreSQL full-text support."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Event, Issue, Message
from codehive.db.models import Session as SessionModel


class SessionNotFoundError(Exception):
    """Raised when a session is not found by ID."""


@dataclass
class SearchResult:
    """Internal search result representation."""

    type: str
    id: uuid.UUID
    snippet: str
    score: float
    created_at: datetime
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    project_name: str | None = None
    session_name: str | None = None


@dataclass
class SearchResults:
    """Paginated search results."""

    results: list[SearchResult]
    total: int
    has_more: bool


_ESCAPE_CHAR = "\\"


def _like_pattern(query: str) -> str:
    """Build a LIKE pattern from a query string.

    Escapes % and _ with the backslash escape character.
    All .ilike() / .like() calls must pass escape=_ESCAPE_CHAR.
    """
    escaped = query.replace(_ESCAPE_CHAR, _ESCAPE_CHAR + _ESCAPE_CHAR)
    escaped = escaped.replace("%", _ESCAPE_CHAR + "%")
    escaped = escaped.replace("_", _ESCAPE_CHAR + "_")
    return f"%{escaped}%"


def _ilike_with_escape(column, pattern: str):
    """Return an ILIKE expression with proper escape character."""
    return column.ilike(pattern, escape=_ESCAPE_CHAR)


def _score_expr(column, pattern: str):
    """Return a simple relevance score: 1.0 if pattern found, 0.5 otherwise.

    This is a simplified scoring for SQLite compatibility.
    For PostgreSQL, this would use ts_rank().
    """
    return case(
        (func.lower(cast(column, String)).contains(pattern.lower()), literal(1.0)),
        else_=literal(0.5),
    )


def _snippet_expr(column):
    """Return the column cast to string for use as a snippet.

    For PostgreSQL, this would use ts_headline().
    For SQLite, we return the raw text (truncated at the application layer).
    """
    return cast(column, String)


def _truncate_snippet(text: str, query: str, max_len: int = 200) -> str:
    """Truncate text to show context around the matched query."""
    if not text:
        return ""
    lower_text = text.lower()
    lower_query = query.lower()
    pos = lower_text.find(lower_query)
    if pos == -1:
        return text[:max_len] + ("..." if len(text) > max_len else "")
    # Show context around the match
    start = max(0, pos - 50)
    end = min(len(text), pos + len(query) + 150)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


async def search(
    db: AsyncSession,
    query: str,
    *,
    entity_type: str | None = None,
    project_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResults:
    """Search across sessions, messages, issues, and events.

    Uses LIKE-based search for SQLite compatibility.
    """
    pattern = _like_pattern(query)

    subqueries = []

    # Sessions: search by name
    if entity_type is None or entity_type == "session":
        session_q = select(
            literal("session").label("type"),
            SessionModel.id.label("id"),
            cast(SessionModel.name, String).label("snippet"),
            literal(1.0).label("score"),
            SessionModel.created_at.label("created_at"),
            SessionModel.project_id.label("project_id"),
            literal(None).label("session_id"),
        ).where(_ilike_with_escape(SessionModel.name, pattern))
        if project_id is not None:
            session_q = session_q.where(SessionModel.project_id == project_id)
        subqueries.append(session_q)

    # Messages: search by content
    if entity_type is None or entity_type == "message":
        message_q = select(
            literal("message").label("type"),
            Message.id.label("id"),
            cast(Message.content, String).label("snippet"),
            literal(1.0).label("score"),
            Message.created_at.label("created_at"),
            literal(None).label("project_id"),
            Message.session_id.label("session_id"),
        ).where(_ilike_with_escape(Message.content, pattern))
        if project_id is not None:
            # Join through session to filter by project
            message_q = message_q.join(SessionModel, Message.session_id == SessionModel.id).where(
                SessionModel.project_id == project_id
            )
        subqueries.append(message_q)

    # Issues: search by title + description
    if entity_type is None or entity_type == "issue":
        issue_q = select(
            literal("issue").label("type"),
            Issue.id.label("id"),
            cast(Issue.title, String).label("snippet"),
            literal(1.0).label("score"),
            Issue.created_at.label("created_at"),
            Issue.project_id.label("project_id"),
            literal(None).label("session_id"),
        ).where(
            or_(
                _ilike_with_escape(Issue.title, pattern),
                _ilike_with_escape(Issue.description, pattern),
            )
        )
        if project_id is not None:
            issue_q = issue_q.where(Issue.project_id == project_id)
        subqueries.append(issue_q)

    # Events: search by type field (data is JSONB, hard to search portably)
    if entity_type is None or entity_type == "event":
        event_q = select(
            literal("event").label("type"),
            Event.id.label("id"),
            cast(Event.type, String).label("snippet"),
            literal(1.0).label("score"),
            Event.created_at.label("created_at"),
            literal(None).label("project_id"),
            Event.session_id.label("session_id"),
        ).where(_ilike_with_escape(Event.type, pattern))
        if project_id is not None:
            event_q = event_q.join(SessionModel, Event.session_id == SessionModel.id).where(
                SessionModel.project_id == project_id
            )
        subqueries.append(event_q)

    if not subqueries:
        return SearchResults(results=[], total=0, has_more=False)

    # Union all subqueries
    combined = union_all(*subqueries).subquery()

    # Count total
    count_stmt = select(func.count()).select_from(combined)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch paginated results ordered by created_at desc
    fetch_stmt = select(combined).order_by(combined.c.created_at.desc()).limit(limit).offset(offset)
    rows = await db.execute(fetch_stmt)

    results = []
    for row in rows:
        snippet_text = row.snippet or ""
        results.append(
            SearchResult(
                type=row.type,
                id=row.id,
                snippet=_truncate_snippet(snippet_text, query),
                score=float(row.score),
                created_at=row.created_at,
                project_id=row.project_id,
                session_id=row.session_id,
            )
        )

    return SearchResults(
        results=results,
        total=total,
        has_more=(offset + limit) < total,
    )


async def search_session_history(
    db: AsyncSession,
    session_id: uuid.UUID,
    query: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> SearchResults:
    """Search within a single session's messages and events.

    Raises SessionNotFoundError if the session does not exist.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    pattern = _like_pattern(query)

    # Messages in this session
    message_q = (
        select(
            literal("message").label("type"),
            Message.id.label("id"),
            cast(Message.content, String).label("snippet"),
            literal(1.0).label("score"),
            Message.created_at.label("created_at"),
        )
        .where(Message.session_id == session_id)
        .where(_ilike_with_escape(Message.content, pattern))
    )

    # Events in this session
    event_q = (
        select(
            literal("event").label("type"),
            Event.id.label("id"),
            cast(Event.type, String).label("snippet"),
            literal(1.0).label("score"),
            Event.created_at.label("created_at"),
        )
        .where(Event.session_id == session_id)
        .where(_ilike_with_escape(Event.type, pattern))
    )

    combined = union_all(message_q, event_q).subquery()

    # Count total
    count_stmt = select(func.count()).select_from(combined)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch paginated results
    fetch_stmt = select(combined).order_by(combined.c.created_at.desc()).limit(limit).offset(offset)
    rows = await db.execute(fetch_stmt)

    results = []
    for row in rows:
        snippet_text = row.snippet or ""
        results.append(
            SearchResult(
                type=row.type,
                id=row.id,
                snippet=_truncate_snippet(snippet_text, query),
                score=float(row.score),
                created_at=row.created_at,
            )
        )

    return SearchResults(
        results=results,
        total=total,
        has_more=(offset + limit) < total,
    )
