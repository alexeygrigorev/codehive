"""query_agent tool schema definition for the native engine."""

from typing import Any

QUERY_AGENT_TOOL: dict[str, Any] = {
    "name": "query_agent",
    "description": (
        "Query another agent's current state including status, mode, "
        "current task, and recent events."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session ID of the agent to query.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of recent events to return (default 10).",
            },
        },
        "required": ["session_id"],
    },
}
