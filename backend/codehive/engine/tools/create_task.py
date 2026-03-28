"""create_task tool schema definition for the native engine."""

from typing import Any

CREATE_TASK_TOOL: dict[str, Any] = {
    "name": "create_task",
    "description": (
        "Create a new task in the project backlog. "
        "Creates an Issue (status 'open') and a Task (pipeline_status 'backlog') "
        "in the current project. The project is resolved from the session context -- "
        "you do not need to pass a project ID. "
        "Returns the issue_id, task_id, and pipeline_status."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for the task (required).",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the task (optional).",
            },
            "acceptance_criteria": {
                "type": "string",
                "description": (
                    "Acceptance criteria in markdown checklist format (optional). "
                    "Example: '- [ ] Sidebar refreshes after creation\\n- [ ] No page reload required'"
                ),
            },
        },
        "required": ["title"],
    },
}
