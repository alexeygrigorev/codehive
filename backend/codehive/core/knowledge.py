"""Project knowledge base: CRUD operations for structured knowledge sections."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.project import ProjectNotFoundError, get_project

# Keys managed by the archetype system -- must not be clobbered
ARCHETYPE_KEYS = {"archetype_roles", "archetype_settings"}


async def get_knowledge(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    """Return the full knowledge dict for a project.

    Raises ProjectNotFoundError if the project does not exist.
    """
    project = await get_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")
    return dict(project.knowledge) if project.knowledge else {}


async def update_knowledge(
    db: AsyncSession,
    project_id: uuid.UUID,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Merge-update knowledge sections on a project.

    Only the keys present in *updates* are modified; all other existing
    keys (including archetype keys) are preserved.

    Raises ProjectNotFoundError if the project does not exist.
    """
    project = await get_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    current = dict(project.knowledge) if project.knowledge else {}
    current.update(updates)

    # Assign a new dict so SQLAlchemy detects the mutation
    project.knowledge = current
    await db.commit()
    await db.refresh(project)
    return dict(project.knowledge)


async def get_charter(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    """Return the charter sub-document from project knowledge.

    Returns ``{}`` if no charter has been set yet.
    Raises ProjectNotFoundError if the project does not exist.
    """
    knowledge = await get_knowledge(db, project_id)
    return knowledge.get("charter", {})


async def set_charter(
    db: AsyncSession,
    project_id: uuid.UUID,
    charter: dict[str, Any],
) -> dict[str, Any]:
    """Replace the charter sub-document within project knowledge.

    Raises ProjectNotFoundError if the project does not exist.
    """
    project = await get_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    current = dict(project.knowledge) if project.knowledge else {}
    current["charter"] = charter

    project.knowledge = current
    await db.commit()
    await db.refresh(project)
    return project.knowledge.get("charter", {})


def build_knowledge_context(knowledge: dict[str, Any]) -> str:
    """Build a system prompt block from project knowledge and charter.

    Returns an empty string if the knowledge dict is empty or contains
    only archetype keys.
    """
    # Filter out archetype-only keys for the prompt
    relevant = {k: v for k, v in knowledge.items() if k not in ARCHETYPE_KEYS}
    if not relevant:
        return ""

    parts: list[str] = ["## Project Knowledge"]

    if "tech_stack" in relevant:
        parts.append(f"\n### Tech Stack\n{_format_dict(relevant['tech_stack'])}")

    if "architecture" in relevant:
        parts.append(f"\n### Architecture\n{_format_dict(relevant['architecture'])}")

    if "conventions" in relevant:
        parts.append(f"\n### Conventions\n{_format_dict(relevant['conventions'])}")

    if "decisions" in relevant:
        parts.append("\n### Decisions")
        for d in relevant["decisions"]:
            title = d.get("title", d.get("id", "unknown"))
            status = d.get("status", "")
            parts.append(f"- {title} ({status})")

    if "open_decisions" in relevant:
        parts.append("\n### Open Decisions")
        for od in relevant["open_decisions"]:
            question = od.get("question", od.get("id", "unknown"))
            parts.append(f"- {question}")

    charter = relevant.get("charter")
    if charter:
        parts.append("\n### Agent Charter")
        if charter.get("goals"):
            parts.append("Goals: " + "; ".join(charter["goals"]))
        if charter.get("constraints"):
            parts.append("Constraints: " + "; ".join(charter["constraints"]))
        if charter.get("tech_stack_rules"):
            parts.append("Tech stack rules: " + "; ".join(charter["tech_stack_rules"]))
        if charter.get("coding_rules"):
            parts.append("Coding rules: " + "; ".join(charter["coding_rules"]))
        if charter.get("decision_policies"):
            parts.append("Decision policies: " + "; ".join(charter["decision_policies"]))

    # Include any extra keys not handled above
    handled = {
        "tech_stack",
        "architecture",
        "conventions",
        "decisions",
        "open_decisions",
        "charter",
    }
    for key, value in relevant.items():
        if key not in handled:
            parts.append(
                f"\n### {key}\n{_format_dict(value) if isinstance(value, dict) else str(value)}"
            )

    return "\n".join(parts)


def _format_dict(d: dict[str, Any]) -> str:
    """Format a dict as key: value lines."""
    return "\n".join(f"- {k}: {v}" for k, v in d.items())
