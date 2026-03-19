"""Parse Codex CLI ``codex exec --json`` JSONL output into codehive event dicts."""

from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)


class CodexCLIParser:
    """Stateless parser that converts Codex CLI JSONL lines into codehive events.

    Each line from ``codex exec --json`` stdout is a JSON object.  This parser
    maps those into the same event dict format used by all codehive engines.

    The parser is defensive: unrecognised event types and malformed JSON are
    logged and skipped rather than causing crashes.
    """

    def parse_line(self, line: str, session_id: uuid.UUID) -> list[dict]:
        """Parse a single JSONL line and return zero or more codehive events.

        Args:
            line: A single line of JSONL output from ``codex exec --json``.
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
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Malformed JSON from Codex CLI: %s", line[:200])
            return []

        if not isinstance(data, dict):
            logger.warning("Expected JSON object, got %s", type(data).__name__)
            return []

        sid = str(session_id)

        # The Codex CLI --json output uses a "type" field to indicate the
        # event kind.  The exact schema may evolve, so we handle known types
        # and skip unknown ones gracefully.
        event_type = data.get("type", "")

        # --- Item completed (real Codex CLI ``exec --json`` format) ---
        if event_type == "item.completed":
            item = data.get("item", {})
            item_type = item.get("type", "")
            if item_type == "agent_message":
                text = item.get("text", "")
                if text:
                    return [
                        {
                            "type": "message.created",
                            "role": "assistant",
                            "content": text,
                            "session_id": sid,
                        }
                    ]
            elif item_type == "error":
                error_msg = item.get("message", str(item))
                return [
                    {
                        "type": "session.error",
                        "error": error_msg,
                        "session_id": sid,
                    }
                ]
            # Other item types (e.g. tool calls) -- skip for now
            return []

        # --- Thread / turn lifecycle events ---
        if event_type == "thread.started":
            return [
                {
                    "type": "session.started",
                    "thread_id": data.get("thread_id", ""),
                    "session_id": sid,
                }
            ]

        if event_type == "turn.started":
            return [
                {
                    "type": "turn.started",
                    "session_id": sid,
                }
            ]

        if event_type == "turn.completed":
            return [
                {
                    "type": "turn.completed",
                    "usage": data.get("usage", {}),
                    "session_id": sid,
                }
            ]

        if event_type == "turn.failed":
            error_info = data.get("error", {})
            error_msg = (
                error_info.get("message", str(error_info))
                if isinstance(error_info, dict)
                else str(error_info)
            )
            return [
                {
                    "type": "session.error",
                    "error": error_msg,
                    "session_id": sid,
                }
            ]

        # --- Agent / assistant text message ---
        if event_type in ("message", "assistant", "response"):
            content = _extract_text(data)
            if content is not None:
                return [
                    {
                        "type": "message.created",
                        "role": "assistant",
                        "content": content,
                        "session_id": sid,
                    }
                ]
            return []

        # --- Streaming text delta ---
        if event_type in ("text_delta", "content_delta"):
            text = data.get("delta", data.get("text", data.get("content", "")))
            if text:
                return [
                    {
                        "type": "message.delta",
                        "role": "assistant",
                        "content": text,
                        "session_id": sid,
                    }
                ]
            return []

        # --- Tool / command execution start ---
        if event_type in ("command", "tool_call", "function_call", "exec"):
            tool_name = data.get("name", data.get("command", data.get("tool", "unknown")))
            tool_input = data.get("input", data.get("args", data.get("arguments", {})))
            return [
                {
                    "type": "tool.call.started",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "session_id": sid,
                }
            ]

        # --- Tool / command execution result ---
        if event_type in ("command_result", "tool_result", "function_result", "exec_result"):
            tool_name = data.get("name", data.get("command", data.get("tool", "unknown")))
            result_content = data.get("output", data.get("result", data.get("content", "")))
            events: list[dict] = [
                {
                    "type": "tool.call.finished",
                    "tool_name": tool_name,
                    "result": result_content,
                    "session_id": sid,
                }
            ]
            # If the result indicates a file change, emit file.changed
            if tool_name in ("edit_file", "write_file", "create_file", "patch"):
                path = data.get("path", data.get("file"))
                if path:
                    events.append(
                        {
                            "type": "file.changed",
                            "path": path,
                            "session_id": sid,
                        }
                    )
            return events

        # --- File change event ---
        if event_type in ("file_change", "file_edit", "patch"):
            path = data.get("path", data.get("file", ""))
            return [
                {
                    "type": "file.changed",
                    "path": path,
                    "session_id": sid,
                }
            ]

        # --- Error ---
        if event_type in ("error", "system_error"):
            error_msg = data.get("error", data.get("message", str(data)))
            return [
                {
                    "type": "session.error",
                    "error": error_msg,
                    "session_id": sid,
                }
            ]

        # Unrecognised type -- skip gracefully
        logger.debug("Skipping unrecognised Codex CLI event type: %s", event_type)
        return []


def _extract_text(data: dict) -> str | None:
    """Extract text content from a Codex CLI message object.

    Handles both plain string content and structured content blocks.
    """
    content = data.get("content", data.get("message", data.get("text")))

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)
        return "".join(texts) if texts else None

    return None
