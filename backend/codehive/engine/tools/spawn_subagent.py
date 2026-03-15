"""spawn_subagent tool schema definition for the native engine."""

from typing import Any

SPAWN_SUBAGENT_TOOL: dict[str, Any] = {
    "name": "spawn_subagent",
    "description": (
        "Spawn a sub-agent session that works on a scoped mission. "
        "The sub-agent inherits the parent's project and engine."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "mission": {
                "type": "string",
                "description": "The mission or goal for the sub-agent.",
            },
            "role": {
                "type": "string",
                "description": "The role of the sub-agent (e.g. 'swe', 'tester', 'pm').",
            },
            "scope": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths the sub-agent should focus on.",
            },
            "config": {
                "type": "object",
                "description": "Optional additional configuration for the sub-agent.",
            },
        },
        "required": ["mission", "role", "scope"],
    },
}
