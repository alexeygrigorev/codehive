"""read_issue tool schema definition for the native engine."""

from typing import Any

READ_ISSUE_TOOL: dict[str, Any] = {
    "name": "read_issue",
    "description": (
        "Read the details of an issue by its ID. "
        "Returns title, description, acceptance_criteria, status, priority, "
        "assigned_agent, timestamps, and all log entries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "issue_id": {
                "type": "string",
                "description": "The UUID of the issue to read (required).",
            },
        },
        "required": ["issue_id"],
    },
}
