"""spawn_team_agent tool schema definition for the native engine."""

from typing import Any

# Role -> default pipeline_step mapping
ROLE_DEFAULT_STEP: dict[str, str] = {
    "pm": "grooming",
    "swe": "implementing",
    "qa": "testing",
    "oncall": "implementing",
}

SPAWN_TEAM_AGENT_TOOL: dict[str, Any] = {
    "name": "spawn_team_agent",
    "description": (
        "Spawn a team agent session bound to a specific task. "
        "Looks up the agent profile from the DB to get name, role, preferred engine, "
        "personality, and system_prompt_modifier. Creates a child session with the "
        "correct engine, role, task binding, and pipeline step. "
        "Returns the session_id, agent_name, role, and engine."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_profile_id": {
                "type": "string",
                "description": "UUID of the agent profile to spawn.",
            },
            "task_id": {
                "type": "string",
                "description": "UUID of the task to assign to the agent.",
            },
            "instructions": {
                "type": "string",
                "description": "Instructions or message for the agent describing what to do.",
            },
            "pipeline_step": {
                "type": "string",
                "description": (
                    "Override the default pipeline step derived from the agent's role. "
                    "E.g. 'accepting' for a PM doing acceptance instead of grooming."
                ),
            },
        },
        "required": ["agent_profile_id", "task_id", "instructions"],
    },
}
