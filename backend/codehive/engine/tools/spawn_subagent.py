"""spawn_subagent tool schema definition for the native engine."""

from typing import Any

VALID_ENGINE_TYPES: set[str] = {
    "native",
    "claude_code",
    "codex_cli",
    "copilot_cli",
    "gemini_cli",
    "codex",
}

SPAWN_SUBAGENT_TOOL: dict[str, Any] = {
    "name": "spawn_subagent",
    "description": (
        "Spawn a sub-agent session that works on a scoped mission. "
        "By default the sub-agent inherits the parent's project and engine, "
        "but you can specify a different engine (e.g. 'claude_code', 'codex_cli'). "
        "If initial_message is provided, the child engine is started immediately "
        "and the response is returned."
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
            "engine": {
                "type": "string",
                "description": (
                    "Engine type for the child session. "
                    "One of: native, claude_code, codex_cli, copilot_cli, gemini_cli, codex. "
                    "Defaults to the parent session's engine."
                ),
            },
            "initial_message": {
                "type": "string",
                "description": (
                    "First message to send to the child session after creation. "
                    "If provided, the child engine is instantiated and this message "
                    "is sent immediately, returning the response."
                ),
            },
            "config": {
                "type": "object",
                "description": "Optional additional configuration for the sub-agent.",
            },
        },
        "required": ["mission", "role", "scope"],
    },
}
