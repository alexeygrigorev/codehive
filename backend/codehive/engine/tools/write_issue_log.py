"""write_issue_log tool schema definition for the native engine."""

from typing import Any

WRITE_ISSUE_LOG_TOOL: dict[str, Any] = {
    "name": "write_issue_log",
    "description": (
        "Append a log entry to an issue. "
        "Use this to record findings, test results, verdicts, or progress updates. "
        "Returns the created log entry with id, issue_id, agent_role, content, and created_at."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "issue_id": {
                "type": "string",
                "description": "The UUID of the issue to write to (required).",
            },
            "agent_role": {
                "type": "string",
                "description": "The role of the agent writing the log entry, e.g. 'swe', 'qa', 'pm' (required).",
            },
            "content": {
                "type": "string",
                "description": "The content of the log entry (required).",
            },
        },
        "required": ["issue_id", "agent_role", "content"],
    },
}
