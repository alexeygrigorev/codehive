"""get_subsession_result tool schema definition for the native engine."""

from typing import Any

GET_SUBSESSION_RESULT_TOOL: dict[str, Any] = {
    "name": "get_subsession_result",
    "description": (
        "Get the structured result of a child subsession. "
        "For completed/failed/blocked sessions, returns a full report "
        "(status, summary, files_changed, tests, warnings). "
        "For in-progress sessions, returns current status with event count. "
        "Only works for sessions that are children of the calling session."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session ID of the child subsession to get results for.",
            },
        },
        "required": ["session_id"],
    },
}
