"""Parse GitHub Copilot CLI JSONL output into codehive event dicts."""

from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)


class CopilotCLIParser:
    """Stateless parser that converts Copilot CLI JSONL lines into codehive events.

    Each line from ``copilot -p --output-format json`` is a JSON object with a
    ``type`` field and a ``data`` dict.  This parser maps those into the same
    event dict format used by all codehive engines.

    The parser is defensive: unrecognised event types and malformed JSON are
    logged and skipped rather than causing crashes.
    """

    def parse_line(self, line: str, session_id: uuid.UUID) -> list[dict]:
        """Parse a single JSONL line and return zero or more codehive events.

        Args:
            line: A single line of JSONL output from the Copilot CLI.
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
            logger.warning("Malformed JSON from Copilot CLI: %s", line[:200])
            return []

        if not isinstance(raw, dict):
            logger.warning("Expected JSON object, got %s", type(raw).__name__)
            return []

        event_type = raw.get("type", "")
        data = raw.get("data", {})
        if not isinstance(data, dict):
            data = {}
        sid = str(session_id)

        # --- Streaming text delta ---
        if event_type == "assistant.message_delta":
            content = data.get("deltaContent", "")
            if content:
                return [
                    {
                        "type": "message.delta",
                        "role": "assistant",
                        "content": content,
                        "session_id": sid,
                    }
                ]
            return []

        # --- Complete assistant message ---
        if event_type == "assistant.message":
            content = data.get("content", "")
            if content:
                return [
                    {
                        "type": "message.created",
                        "role": "assistant",
                        "content": content,
                        "session_id": sid,
                    }
                ]
            return []

        # --- Tool execution start ---
        if event_type == "tool.execution_start":
            tool_name = data.get("toolName", "unknown")
            tool_input = data.get("arguments", {})
            return [
                {
                    "type": "tool.call.started",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "session_id": sid,
                }
            ]

        # --- Tool execution complete ---
        if event_type == "tool.execution_complete":
            tool_name = data.get("toolName", "unknown")
            success = data.get("success", True)
            result_data = data.get("result", {})

            if isinstance(result_data, dict):
                result_content = result_data.get("content", result_data.get("detailedContent", ""))
            else:
                result_content = str(result_data)

            if not success:
                result_content = f"ERROR: {result_content}"

            events: list[dict] = [
                {
                    "type": "tool.call.finished",
                    "tool_name": tool_name,
                    "result": result_content,
                    "session_id": sid,
                }
            ]

            # If tool is a file-editing tool, also emit file.changed
            if tool_name in ("write", "edit", "create", "write_file", "edit_file"):
                path = (
                    data.get("arguments", {}).get("path", "")
                    if isinstance(data.get("arguments"), dict)
                    else ""
                )
                if path:
                    events.append(
                        {
                            "type": "file.changed",
                            "path": path,
                            "session_id": sid,
                        }
                    )

            return events

        # --- Session tools updated (model ready) ---
        if event_type == "session.tools_updated":
            model = data.get("model", "")
            return [
                {
                    "type": "session.started",
                    "session_id": sid,
                    "model": model,
                }
            ]

        # --- Final result event ---
        if event_type == "result":
            copilot_session_id = raw.get("sessionId", "")
            usage = raw.get("usage", {})
            return [
                {
                    "type": "session.completed",
                    "session_id": sid,
                    "copilot_session_id": copilot_session_id,
                    "usage": usage if isinstance(usage, dict) else {},
                }
            ]

        # --- Skip ephemeral and internal events ---
        skip_types = {
            "session.mcp_server_status_changed",
            "session.mcp_servers_loaded",
            "user.message",
            "assistant.turn_start",
            "assistant.reasoning_delta",
            "assistant.reasoning",
            "assistant.turn_end",
            "session.background_tasks_changed",
        }
        if event_type in skip_types:
            return []

        # Unrecognised type -- skip gracefully
        logger.debug("Skipping unrecognised Copilot CLI event type: %s", event_type)
        return []
