"""Search service with SQLite LIKE fallback and PostgreSQL full-text support."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, case, cast, column, func, literal, or_, select, union_all
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

# ts_headline options for PostgreSQL FTS snippet highlighting
_TS_HEADLINE_OPTIONS = "StartSel='<b>', StopSel='</b>'"


def _like_pattern(query: str) -> str:
    """Build a LIKE pattern from a query string.

    Escapes % and _ with the backslash escape character.
    All .ilike() / .like() calls must pass escape=_ESCAPE_CHAR.
    """
    escaped = query.replace(_ESCAPE_CHAR, _ESCAPE_CHAR + _ESCAPE_CHAR)
    escaped = escaped.replace("%", _ESCAPE_CHAR + "%")
    escaped = escaped.replace("_", _ESCAPE_CHAR + "_")
    return f"%{escaped}%"


def _ilike_with_escape(col, pattern: str):
    """Return an ILIKE expression with proper escape character."""
    return col.ilike(pattern, escape=_ESCAPE_CHAR)


def _score_expr(col, pattern: str):
    """Return a simple relevance score: 1.0 if pattern found, 0.5 otherwise.

    This is a simplified scoring for SQLite compatibility.
    For PostgreSQL, this would use ts_rank().
    """
    return case(
        (func.lower(cast(col, String)).contains(pattern.lower()), literal(1.0)),
        else_=literal(0.5),
    )


def _snippet_expr(col):
    """Return the column cast to string for use as a snippet.

    For PostgreSQL, this would use ts_headline().
    For SQLite, we return the raw text (truncated at the application layer).
    """
    return cast(col, String)


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


def _is_postgresql(db: AsyncSession) -> bool:
    """Check if the database dialect is PostgreSQL."""
    return db.bind.dialect.name == "postgresql"


def _fts_match(query: str):
    """Return a plainto_tsquery expression for PostgreSQL FTS matching."""
    return func.plainto_tsquery("english", query)


def _fts_rank(query: str):
    """Return a ts_rank expression using the search_vector column."""
    return func.ts_rank(column("search_vector"), _fts_match(query))


def _fts_headline(source_col, query: str):
    """Return a ts_headline expression for snippet highlighting."""
    return func.ts_headline(
        "english",
        source_col,
        _fts_match(query),
        _TS_HEADLINE_OPTIONS,
    )


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

    Uses PostgreSQL FTS when available, falls back to ILIKE for SQLite.
    """
    use_fts = _is_postgresql(db)
    pattern = _like_pattern(query)

    subqueries = []

    # Sessions: search by name
    if entity_type is None or entity_type == "session":
        if use_fts:
            tsquery = _fts_match(query)
            session_q = select(
                literal("session").label("type"),
                SessionModel.id.label("id"),
                _fts_headline(SessionModel.name, query).label("snippet"),
                _fts_rank(query).label("score"),
                SessionModel.created_at.label("created_at"),
                SessionModel.project_id.label("project_id"),
                literal(None).label("session_id"),
            ).where(column("search_vector").op("@@")(tsquery))
        else:
            session_q = select(
                literal("session").label("type"),
                SessionModel.id.label("id"),
                cast(SessionModel.name, String).label("snippet"),
                literal(1.0).label("score"),
                SessionModel.created_at.label("created_at"),
                SessionModel.project_id.label("project_id"),
                literal(None).label("session_id"),
            ).where(_ilike_with_escape(SessionModel.name, pattern))
        session_q = session_q.select_from(SessionModel.__table__)
        if project_id is not None:
            session_q = session_q.where(SessionModel.project_id == project_id)
        subqueries.append(session_q)

    # Messages: search by content
    if entity_type is None or entity_type == "message":
        if use_fts:
            tsquery = _fts_match(query)
            message_q = select(
                literal("message").label("type"),
                Message.id.label("id"),
                _fts_headline(Message.content, query).label("snippet"),
                _fts_rank(query).label("score"),
                Message.created_at.label("created_at"),
                literal(None).label("project_id"),
                Message.session_id.label("session_id"),
            ).where(column("search_vector").op("@@")(tsquery))
        else:
            message_q = select(
                literal("message").label("type"),
                Message.id.label("id"),
                cast(Message.content, String).label("snippet"),
                literal(1.0).label("score"),
                Message.created_at.label("created_at"),
                literal(None).label("project_id"),
                Message.session_id.label("session_id"),
            ).where(_ilike_with_escape(Message.content, pattern))
        message_q = message_q.select_from(Message.__table__)
        if project_id is not None:
            message_q = message_q.join(SessionModel, Message.session_id == SessionModel.id).where(
                SessionModel.project_id == project_id
            )
        subqueries.append(message_q)

    # Issues: search by title + description
    if entity_type is None or entity_type == "issue":
        if use_fts:
            tsquery = _fts_match(query)
            issue_q = select(
                literal("issue").label("type"),
                Issue.id.label("id"),
                _fts_headline(Issue.title, query).label("snippet"),
                _fts_rank(query).label("score"),
                Issue.created_at.label("created_at"),
                Issue.project_id.label("project_id"),
                literal(None).label("session_id"),
            ).where(column("search_vector").op("@@")(tsquery))
        else:
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
        issue_q = issue_q.select_from(Issue.__table__)
        if project_id is not None:
            issue_q = issue_q.where(Issue.project_id == project_id)
        subqueries.append(issue_q)

    # Events: search by type field
    if entity_type is None or entity_type == "event":
        if use_fts:
            tsquery = _fts_match(query)
            event_q = select(
                literal("event").label("type"),
                Event.id.label("id"),
                _fts_headline(Event.type, query).label("snippet"),
                _fts_rank(query).label("score"),
                Event.created_at.label("created_at"),
                literal(None).label("project_id"),
                Event.session_id.label("session_id"),
            ).where(column("search_vector").op("@@")(tsquery))
        else:
            event_q = select(
                literal("event").label("type"),
                Event.id.label("id"),
                cast(Event.type, String).label("snippet"),
                literal(1.0).label("score"),
                Event.created_at.label("created_at"),
                literal(None).label("project_id"),
                Event.session_id.label("session_id"),
            ).where(_ilike_with_escape(Event.type, pattern))
        event_q = event_q.select_from(Event.__table__)
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

    # Order by relevance (ts_rank) on PostgreSQL, by created_at on SQLite
    if use_fts:
        fetch_stmt = select(combined).order_by(combined.c.score.desc()).limit(limit).offset(offset)
    else:
        fetch_stmt = (
            select(combined).order_by(combined.c.created_at.desc()).limit(limit).offset(offset)
        )
    rows = await db.execute(fetch_stmt)

    results = []
    for row in rows:
        snippet_text = row.snippet or ""
        # On PostgreSQL, ts_headline already provides highlighted snippets
        if use_fts:
            snippet = snippet_text
        else:
            snippet = _truncate_snippet(snippet_text, query)
        results.append(
            SearchResult(
                type=row.type,
                id=row.id,
                snippet=snippet,
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
    Uses PostgreSQL FTS when available, falls back to ILIKE for SQLite.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    use_fts = _is_postgresql(db)
    pattern = _like_pattern(query)

    # Messages in this session
    if use_fts:
        tsquery = _fts_match(query)
        message_q = (
            select(
                literal("message").label("type"),
                Message.id.label("id"),
                _fts_headline(Message.content, query).label("snippet"),
                _fts_rank(query).label("score"),
                Message.created_at.label("created_at"),
            )
            .select_from(Message.__table__)
            .where(Message.session_id == session_id)
            .where(column("search_vector").op("@@")(tsquery))
        )
    else:
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
    if use_fts:
        tsquery = _fts_match(query)
        event_q = (
            select(
                literal("event").label("type"),
                Event.id.label("id"),
                _fts_headline(Event.type, query).label("snippet"),
                _fts_rank(query).label("score"),
                Event.created_at.label("created_at"),
            )
            .select_from(Event.__table__)
            .where(Event.session_id == session_id)
            .where(column("search_vector").op("@@")(tsquery))
        )
    else:
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

    # Order by relevance on PostgreSQL, by created_at on SQLite
    if use_fts:
        fetch_stmt = select(combined).order_by(combined.c.score.desc()).limit(limit).offset(offset)
    else:
        fetch_stmt = (
            select(combined).order_by(combined.c.created_at.desc()).limit(limit).offset(offset)
        )
    rows = await db.execute(fetch_stmt)

    results = []
    for row in rows:
        snippet_text = row.snippet or ""
        if use_fts:
            snippet = snippet_text
        else:
            snippet = _truncate_snippet(snippet_text, query)
        results.append(
            SearchResult(
                type=row.type,
                id=row.id,
                snippet=snippet,
                score=float(row.score),
                created_at=row.created_at,
            )
        )

    return SearchResults(
        results=results,
        total=total,
        has_more=(offset + limit) < total,
    )
