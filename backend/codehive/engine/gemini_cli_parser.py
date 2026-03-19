"""Parse Gemini CLI JSONL output into codehive event dicts."""

from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)

# File-editing tool names that should trigger file.changed events.
_FILE_EDIT_TOOLS = frozenset({"write_file", "edit_file"})


class GeminiCLIParser:
    """Stateful parser that converts Gemini CLI JSONL lines into codehive events.

    Each line from ``gemini -p --output-format stream-json`` is a JSON object
    with a ``type`` field.  This parser maps those into the same event dict
    format used by all codehive engines.

    **Statefulness:** Unlike the Copilot parser, ``tool_result`` events in
    Gemini do not repeat ``tool_name`` -- they only carry ``tool_id``.  The
    parser therefore tracks ``tool_id -> tool_name`` and
    ``tool_id -> parameters`` from ``tool_use`` events so that
    ``tool_result`` can emit ``file.changed`` for file-editing tools and
    extract the file path from the original parameters.
    """

    def __init__(self) -> None:
        self._tool_names: dict[str, str] = {}
        self._tool_params: dict[str, dict] = {}
        self._gemini_session_id: str | None = None

    def parse_line(self, line: str, session_id: uuid.UUID) -> list[dict]:
        """Parse a single JSONL line and return zero or more codehive events.

        Args:
            line: A single line of JSONL output from the Gemini CLI.
            session_id: The session this output belongs to.

        Returns:
            A list of event dicts, each containing at least ``type`` and
            ``session_id`` keys.  Returns an empty list for blank lines,
            unrecognised event types, or malformed JSON.
        """
        line = line.strip()
        if not line:
            return []

        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Malformed JSON from Gemini CLI: %s", line[:200])
            return []

        if not isinstance(raw, dict):
            logger.warning("Expected JSON object, got %s", type(raw).__name__)
            return []

        event_type = raw.get("type", "")
        sid = str(session_id)

        # --- Init event: session started ---
        if event_type == "init":
            gemini_sid = raw.get("session_id", "")
            self._gemini_session_id = gemini_sid or self._gemini_session_id
            model = raw.get("model", "")
            return [
                {
                    "type": "session.started",
                    "session_id": sid,
                    "gemini_session_id": gemini_sid,
                    "model": model,
                }
            ]

        # --- Message events ---
        if event_type == "message":
            role = raw.get("role", "")

            # Skip user message echo
            if role == "user":
                return []

            if role == "assistant":
                content = raw.get("content", "")
                is_delta = raw.get("delta", False)

                if is_delta:
                    if not content:
                        return []
                    return [
                        {
                            "type": "message.delta",
                            "role": "assistant",
                            "content": content,
                            "session_id": sid,
                        }
                    ]
                else:
                    if not content:
                        return []
                    return [
                        {
                            "type": "message.created",
                            "role": "assistant",
                            "content": content,
                            "session_id": sid,
                        }
                    ]

            return []

        # --- Tool use: started ---
        if event_type == "tool_use":
            tool_name = raw.get("tool_name", "unknown")
            tool_id = raw.get("tool_id", "")
            parameters = raw.get("parameters", {})
            if not isinstance(parameters, dict):
                parameters = {}

            # Track for later tool_result correlation
            if tool_id:
                self._tool_names[tool_id] = tool_name
                self._tool_params[tool_id] = parameters

            return [
                {
                    "type": "tool.call.started",
                    "tool_name": tool_name,
                    "tool_input": parameters,
                    "session_id": sid,
                }
            ]

        # --- Tool result: finished ---
        if event_type == "tool_result":
            tool_id = raw.get("tool_id", "")
            status = raw.get("status", "")
            output = raw.get("output", "")

            # Determine result content
            if status == "error":
                error_info = raw.get("error", {})
                error_msg = error_info.get("message", "") if isinstance(error_info, dict) else ""
                result_content = f"ERROR: {error_msg}"
            else:
                result_content = (
                    output if isinstance(output, str) else str(output) if output else ""
                )

            # Look up tool_name from tracked tool_use events
            tool_name = self._tool_names.get(tool_id, "unknown")

            events: list[dict] = [
                {
                    "type": "tool.call.finished",
                    "tool_name": tool_name,
                    "result": result_content,
                    "session_id": sid,
                }
            ]

            # Emit file.changed for file-editing tools
            if tool_name in _FILE_EDIT_TOOLS:
                params = self._tool_params.get(tool_id, {})
                file_path = params.get("file_path", "") or params.get("path", "")
                if file_path:
                    events.append(
                        {
                            "type": "file.changed",
                            "path": file_path,
                            "session_id": sid,
                        }
                    )

            return events

        # --- Result event: session completed ---
        if event_type == "result":
            stats = raw.get("stats", {})
            if not isinstance(stats, dict):
                stats = {}

            usage = {}
            if stats:
                usage = {
                    "total_tokens": stats.get("total_tokens", 0),
                    "input_tokens": stats.get("input_tokens", 0),
                    "output_tokens": stats.get("output_tokens", 0),
                    "duration_ms": stats.get("duration_ms", 0),
                    "models": stats.get("models", {}),
                }

            return [
                {
                    "type": "session.completed",
                    "session_id": sid,
                    "gemini_session_id": self._gemini_session_id or "",
                    "usage": usage,
                }
            ]

        # Unrecognised type -- skip gracefully
        logger.debug("Skipping unrecognised Gemini CLI event type: %s", event_type)
        return []
