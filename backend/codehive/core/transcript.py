"""Transcript service: build human-readable session transcripts from messages and events."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import SessionNotFoundError
from codehive.db.models import Event, Message
from codehive.db.models import Session as SessionModel


class TranscriptService:
    """Assembles a session transcript from stored messages and tool-call events."""

    async def _get_session(self, db: AsyncSession, session_id: uuid.UUID) -> SessionModel:
        """Return the session or raise SessionNotFoundError."""
        session = await db.get(SessionModel, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return session

    async def _get_messages(self, db: AsyncSession, session_id: uuid.UUID) -> list[Message]:
        """Fetch all messages for a session ordered by created_at."""
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_tool_events(self, db: AsyncSession, session_id: uuid.UUID) -> list[Event]:
        """Fetch tool.call.started and tool.call.finished events for a session."""
        stmt = (
            select(Event)
            .where(
                Event.session_id == session_id,
                Event.type.in_(["tool.call.started", "tool.call.finished"]),
            )
            .order_by(Event.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _build_entries(self, db: AsyncSession, session_id: uuid.UUID) -> list[dict]:
        """Build a unified timeline of transcript entries from messages and tool calls."""
        messages = await self._get_messages(db, session_id)
        tool_events = await self._get_tool_events(db, session_id)

        # Pair tool.call.started with tool.call.finished by call_id
        started_map: dict[str, Event] = {}
        tool_calls: list[dict] = []

        for ev in tool_events:
            call_id = ev.data.get("call_id", str(ev.id))
            if ev.type == "tool.call.started":
                started_map[call_id] = ev
            elif ev.type == "tool.call.finished":
                start_ev = started_map.pop(call_id, None)
                timestamp = start_ev.created_at if start_ev else ev.created_at
                tool_name = start_ev.data.get("tool_name", "unknown") if start_ev else "unknown"
                tool_input = start_ev.data.get("input") if start_ev else None
                tool_calls.append(
                    {
                        "type": "tool_call",
                        "timestamp": timestamp,
                        "tool_name": tool_name,
                        "input": str(tool_input) if tool_input is not None else None,
                        "output": str(ev.data.get("output", "")) if ev.data.get("output") else None,
                        "is_error": ev.data.get("is_error", False),
                    }
                )

        # Include unmatched started events (no finish yet)
        for call_id, ev in started_map.items():
            tool_calls.append(
                {
                    "type": "tool_call",
                    "timestamp": ev.created_at,
                    "tool_name": ev.data.get("tool_name", "unknown"),
                    "input": str(ev.data.get("input"))
                    if ev.data.get("input") is not None
                    else None,
                    "output": None,
                    "is_error": None,
                }
            )

        # Build message entries
        message_entries = [
            {
                "type": "message",
                "timestamp": msg.created_at,
                "role": msg.role,
                "content": msg.content,
            }
            for msg in messages
        ]

        # Merge and sort by timestamp
        all_entries = message_entries + tool_calls
        all_entries.sort(key=lambda e: e["timestamp"])

        return all_entries

    async def render_json(self, db: AsyncSession, session_id: uuid.UUID) -> dict:
        """Render the transcript as a structured JSON-serializable dict.

        Returns:
            Dict matching the TranscriptExportJSON schema.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        session = await self._get_session(db, session_id)
        entries = await self._build_entries(db, session_id)

        return {
            "session_id": session.id,
            "session_name": session.name,
            "status": session.status,
            "engine": session.engine,
            "mode": session.mode,
            "created_at": session.created_at,
            "exported_at": datetime.now(timezone.utc),
            "entry_count": len(entries),
            "entries": entries,
        }

    async def render_markdown(self, db: AsyncSession, session_id: uuid.UUID) -> str:
        """Render the transcript as a markdown string.

        Returns:
            Markdown-formatted transcript string.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        session = await self._get_session(db, session_id)
        entries = await self._build_entries(db, session_id)

        lines: list[str] = []

        # Session header
        lines.append(f"# Session: {session.name}")
        lines.append("")
        lines.append(f"- **Status:** {session.status}")
        lines.append(f"- **Engine:** {session.engine}")
        lines.append(f"- **Mode:** {session.mode}")
        lines.append(f"- **Created:** {session.created_at.isoformat()}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for entry in entries:
            ts = entry["timestamp"]
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

            if entry["type"] == "message":
                role = entry.get("role", "unknown").capitalize()
                lines.append(f"### {role} ({ts_str})")
                lines.append("")
                lines.append(entry.get("content", ""))
                lines.append("")
            elif entry["type"] == "tool_call":
                tool_name = entry.get("tool_name", "unknown")
                lines.append(f"### Tool Call: {tool_name} ({ts_str})")
                lines.append("")
                if entry.get("input") is not None:
                    lines.append("**Input:**")
                    lines.append("```")
                    lines.append(str(entry["input"]))
                    lines.append("```")
                    lines.append("")
                if entry.get("output") is not None:
                    is_error = entry.get("is_error", False)
                    label = "Error:" if is_error else "Output:"
                    lines.append(f"**{label}**")
                    lines.append("```")
                    lines.append(str(entry["output"]))
                    lines.append("```")
                    lines.append("")

        return "\n".join(lines)
