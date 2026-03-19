"""Parse Claude Code CLI stream-json output into codehive event dicts."""

from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)


class ClaudeCodeParser:
    """Stateless parser that converts Claude Code stream-json lines into codehive events.

    Each line from the Claude Code CLI ``--output-format stream-json`` is a JSON
    object with a ``type`` field.  This parser maps those into the same event dict
    format used by :class:`~codehive.engine.zai_engine.ZaiEngine`.

    The parser is a pure-function style class with no side effects, making it
    straightforward to unit test.
    """

    def parse_line(self, line: str, session_id: uuid.UUID) -> list[dict]:
        """Parse a single stream-json line and return zero or more codehive events.

        Args:
            line: A single line of stream-json output from the Claude Code CLI.
            session_id: The session this output belongs to.

        Returns:
            A list of event dicts, each containing at least ``type`` and
            ``session_id`` keys.  Returns an empty list for blank lines,
            unrecognised message types, or malformed JSON.
        """
        line = line.strip()
        if not line:
            return []

        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Malformed JSON from Claude Code CLI: %s", line[:200])
            return []

        if not isinstance(data, dict):
            logger.warning("Expected JSON object, got %s", type(data).__name__)
            return []

        msg_type = data.get("type", "")
        sid = str(session_id)

        # --- Assistant text message ---
        if msg_type == "assistant":
            content = _extract_text_content(data)
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

        # --- Tool use (tool call started) ---
        if msg_type == "tool_use":
            tool_name = data.get("name", data.get("tool_name", "unknown"))
            tool_input = data.get("input", data.get("tool_input", {}))
            return [
                {
                    "type": "tool.call.started",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "session_id": sid,
                }
            ]

        # --- Tool result (tool call finished) ---
        if msg_type == "tool_result":
            tool_name = data.get("name", data.get("tool_name", "unknown"))
            result_content = data.get("content", data.get("output", ""))
            events: list[dict] = [
                {
                    "type": "tool.call.finished",
                    "tool_name": tool_name,
                    "result": result_content,
                    "session_id": sid,
                }
            ]
            # If the tool result indicates a file change, also emit file.changed
            if tool_name in ("edit_file", "write_file", "create_file"):
                path = data.get("path", data.get("input", {}).get("path"))
                if path:
                    events.append(
                        {
                            "type": "file.changed",
                            "path": path,
                            "session_id": sid,
                        }
                    )
            return events

        # --- Content block delta (streaming text) ---
        if msg_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
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

        # --- System init (captures claude session_id for --resume) ---
        if msg_type == "system" and data.get("subtype") == "init":
            return [
                {
                    "type": "session.started",
                    "session_id": sid,
                    "claude_session_id": data.get("session_id", ""),
                    "model": data.get("model", ""),
                }
            ]

        # --- System message / error ---
        if msg_type in ("error", "system"):
            error_msg = data.get("error", data.get("message", str(data)))
            return [
                {
                    "type": "session.error",
                    "error": error_msg,
                    "session_id": sid,
                }
            ]

        # --- Rate limit event (plan usage data) ---
        if msg_type == "rate_limit_event":
            info = data.get("rate_limit_info", {})
            if isinstance(info, dict) and "utilization" in info:
                return [
                    {
                        "type": "rate_limit.updated",
                        "session_id": sid,
                        "rate_limit_type": info.get("rateLimitType", "unknown"),
                        "utilization": float(info.get("utilization", 0)),
                        "resets_at": info.get("resetsAt", 0),
                        "is_using_overage": bool(info.get("isUsingOverage", False)),
                        "surpassed_threshold": info.get("surpassedThreshold"),
                    }
                ]
            return []

        # --- Result message (final response) ---
        if msg_type == "result":
            result_events: list[dict] = []
            content = _extract_text_content(data)
            if content is not None:
                result_events.append(
                    {
                        "type": "message.created",
                        "role": "assistant",
                        "content": content,
                        "session_id": sid,
                    }
                )

            # Extract per-model usage breakdown if present
            model_usage = data.get("modelUsage")
            if isinstance(model_usage, dict) and model_usage:
                models = []
                for model_name, usage_data in model_usage.items():
                    if isinstance(usage_data, dict):
                        models.append(
                            {
                                "model": model_name,
                                "input_tokens": usage_data.get("inputTokens", 0),
                                "output_tokens": usage_data.get("outputTokens", 0),
                                "cache_read_tokens": usage_data.get("cacheReadInputTokens", 0),
                                "cache_creation_tokens": usage_data.get(
                                    "cacheCreationInputTokens", 0
                                ),
                                "cost_usd": usage_data.get("costUSD", 0),
                                "context_window": usage_data.get("contextWindow"),
                            }
                        )
                if models:
                    result_events.append(
                        {
                            "type": "usage.model_breakdown",
                            "session_id": sid,
                            "models": models,
                            "total_cost_usd": data.get("total_cost_usd", 0),
                        }
                    )

            return result_events

        # Unrecognised type -- skip silently
        logger.debug("Skipping unrecognised Claude Code message type: %s", msg_type)
        return []


def _extract_text_content(data: dict) -> str | None:
    """Extract text content from a Claude Code message object.

    The message may have content as a plain string, or as a list of content
    blocks (each with a ``type`` and ``text`` field).

    Real Claude CLI formats handled:

    - ``{"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}``
    - ``{"type": "result", "result": "final text", ...}``
    - ``{"content": "plain string"}``
    - ``{"content": [{"type": "text", "text": "..."}]}``
    """
    # First, check for a top-level "result" string (used by result events)
    result_field = data.get("result")
    if isinstance(result_field, str) and result_field:
        return result_field

    content = data.get("content", data.get("message"))

    # If "message" is a nested dict (real assistant event format), look inside it
    if isinstance(content, dict):
        content = content.get("content")

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
