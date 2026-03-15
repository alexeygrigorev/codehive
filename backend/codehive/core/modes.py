"""Agent mode system: mode definitions, tool filtering, and system prompts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModeNotFoundError(Exception):
    """Raised when a mode name cannot be resolved."""


class ModeDefinition(BaseModel):
    """Pydantic model for an agent mode definition."""

    name: str
    display_name: str = ""
    description: str = ""
    system_prompt: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mode definitions
# ---------------------------------------------------------------------------

MODES: dict[str, ModeDefinition] = {
    "brainstorm": ModeDefinition(
        name="brainstorm",
        display_name="Brainstorm",
        description="Free-form ideation mode.",
        system_prompt=(
            "You are in brainstorm mode. Focus on free-form ideation: ask open "
            "questions, propose alternatives, and identify gaps. Do not rush to "
            "implementation. Explore ideas broadly before narrowing down."
        ),
        allowed_tools=["read_file", "search_files"],
        denied_tools=["edit_file", "run_shell", "git_commit", "spawn_subagent"],
    ),
    "interview": ModeDefinition(
        name="interview",
        display_name="Interview",
        description="Structured requirements gathering mode.",
        system_prompt=(
            "You are in interview mode. Conduct structured requirements gathering. "
            "Ask batched questions (3-7 per batch). Save answers to project knowledge. "
            "Produce a project spec as the outcome."
        ),
        allowed_tools=["read_file", "search_files"],
        denied_tools=["edit_file", "run_shell", "git_commit", "spawn_subagent"],
    ),
    "planning": ModeDefinition(
        name="planning",
        display_name="Planning",
        description="Turn ideas into structure: milestones, sessions, tasks.",
        system_prompt=(
            "You are in planning mode. Turn ideas into structure: milestones, "
            "sessions, and tasks. Show decided vs. open items clearly. "
            "Do not write code."
        ),
        allowed_tools=["read_file", "search_files", "run_shell"],
        denied_tools=["edit_file", "git_commit"],
    ),
    "execution": ModeDefinition(
        name="execution",
        display_name="Execution",
        description="Standard coding mode with all tools available.",
        system_prompt=(
            "You are in execution mode. Edit files, run commands, execute tasks, "
            "and create sub-agents as needed. Focus on getting the work done."
        ),
        allowed_tools=[],
        denied_tools=[],
    ),
    "review": ModeDefinition(
        name="review",
        display_name="Review",
        description="Evaluate what has been done. Read-only.",
        system_prompt=(
            "You are in review mode. Evaluate what has been done. Check quality, "
            "propose improvements, and prepare next steps. This is a read-only mode."
        ),
        allowed_tools=["read_file", "search_files", "run_shell"],
        denied_tools=["edit_file", "git_commit", "spawn_subagent"],
    ),
}

VALID_MODES: set[str] = set(MODES.keys())


def get_mode(name: str) -> ModeDefinition:
    """Return the mode definition for the given name.

    Raises ModeNotFoundError if the name is not a valid mode.
    """
    mode = MODES.get(name)
    if mode is None:
        raise ModeNotFoundError(f"Mode '{name}' not found")
    return mode


def filter_tools_for_mode(
    tool_definitions: list[dict[str, Any]],
    mode: ModeDefinition,
) -> list[dict[str, Any]]:
    """Filter tool definitions based on a mode's allowed_tools and denied_tools.

    - If allowed_tools is non-empty, only those tools are kept.
    - denied_tools are always removed (takes priority over allowed_tools).
    - If both are empty/unset, all tools are returned (execution mode).
    """
    tools = tool_definitions

    if mode.allowed_tools:
        allowed = set(mode.allowed_tools)
        tools = [t for t in tools if t.get("name") in allowed]

    if mode.denied_tools:
        denied = set(mode.denied_tools)
        tools = [t for t in tools if t.get("name") not in denied]

    return tools


def build_mode_system_prompt(mode: ModeDefinition) -> str:
    """Return the mode's system prompt text."""
    return mode.system_prompt
