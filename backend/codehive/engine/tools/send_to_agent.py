"""send_to_agent tool schema definition for the native engine."""

from typing import Any

SEND_TO_AGENT_TOOL: dict[str, Any] = {
    "name": "send_to_agent",
    "description": (
        "Send a message to another agent. The message is stored as an event "
        "on both the target and sender session event streams."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session ID of the target agent to send the message to.",
            },
            "message": {
                "type": "string",
                "description": "The message text to send to the target agent.",
            },
        },
        "required": ["session_id", "message"],
    },
}
