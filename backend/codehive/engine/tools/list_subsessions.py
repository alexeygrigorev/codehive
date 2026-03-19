"""list_subsessions tool schema definition for the native engine."""

from typing import Any

LIST_SUBSESSIONS_TOOL: dict[str, Any] = {
    "name": "list_subsessions",
    "description": (
        "List all child subsessions of the calling session. "
        "Returns a list with each child's id, name, engine, and status."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
