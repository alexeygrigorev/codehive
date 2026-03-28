"""Spawn configuration helpers: prompt templates and engine config.

Custom prompt templates and engine CLI flags are stored in
``Project.knowledge`` under the keys ``prompt_templates`` and
``engine_config``.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.project import ProjectNotFoundError, get_project
from codehive.core.roles import BUILTIN_ROLES
from codehive.db.models import Project


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


def get_prompt_templates(project: Project) -> list[dict[str, Any]]:
    """Return merged prompt templates for all built-in roles.

    Custom prompts from ``project.knowledge["prompt_templates"]`` override
    the defaults from ``BUILTIN_ROLES``.
    """
    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    custom_templates: dict[str, dict[str, Any]] = knowledge.get("prompt_templates", {})

    result: list[dict[str, Any]] = []
    for role_name, role_def in BUILTIN_ROLES.items():
        custom = custom_templates.get(role_name)
        if custom and custom.get("system_prompt"):
            result.append(
                {
                    "role": role_name,
                    "display_name": role_def["display_name"],
                    "system_prompt": custom["system_prompt"],
                    "is_custom": True,
                }
            )
        else:
            result.append(
                {
                    "role": role_name,
                    "display_name": role_def["display_name"],
                    "system_prompt": role_def["system_prompt"],
                    "is_custom": False,
                }
            )
    return result


def get_system_prompt_for_role(project: Project, role: str) -> str:
    """Return the effective system prompt for *role* on *project*.

    Uses custom template if set, otherwise falls back to BUILTIN_ROLES default.
    """
    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    custom_templates: dict[str, dict[str, Any]] = knowledge.get("prompt_templates", {})
    custom = custom_templates.get(role)
    if custom and custom.get("system_prompt"):
        return custom["system_prompt"]
    role_def = BUILTIN_ROLES.get(role)
    if role_def:
        return role_def["system_prompt"]
    return ""


async def set_prompt_template(
    db: AsyncSession,
    project_id: uuid.UUID,
    role: str,
    system_prompt: str,
) -> dict[str, Any]:
    """Save a custom system prompt for *role* on a project.

    Returns the template dict for the role (with ``is_custom=True``).
    """
    project = await get_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    templates = knowledge.get("prompt_templates", {})
    templates[role] = {"system_prompt": system_prompt}
    knowledge["prompt_templates"] = templates

    project.knowledge = knowledge
    await db.commit()
    await db.refresh(project)

    role_def = BUILTIN_ROLES.get(role, {})
    return {
        "role": role,
        "display_name": role_def.get("display_name", role),
        "system_prompt": system_prompt,
        "is_custom": True,
    }


async def delete_prompt_template(
    db: AsyncSession,
    project_id: uuid.UUID,
    role: str,
) -> dict[str, Any]:
    """Reset *role* to the built-in default prompt.

    Returns the template dict for the role (with ``is_custom=False``).
    """
    project = await get_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    templates = knowledge.get("prompt_templates", {})
    templates.pop(role, None)
    knowledge["prompt_templates"] = templates

    project.knowledge = knowledge
    await db.commit()
    await db.refresh(project)

    role_def = BUILTIN_ROLES.get(role, {})
    return {
        "role": role,
        "display_name": role_def.get("display_name", role),
        "system_prompt": role_def.get("system_prompt", ""),
        "is_custom": False,
    }


# ---------------------------------------------------------------------------
# Engine config
# ---------------------------------------------------------------------------


def get_engine_config(project: Project) -> list[dict[str, Any]]:
    """Return all engine configurations stored on the project."""
    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    engine_config: dict[str, dict[str, Any]] = knowledge.get("engine_config", {})

    result: list[dict[str, Any]] = []
    for engine_name, config in engine_config.items():
        result.append(
            {
                "engine": engine_name,
                "extra_args": config.get("extra_args", []),
            }
        )
    return result


def get_engine_extra_args(project: Project, engine: str) -> list[str]:
    """Return the extra CLI args for *engine* on *project*, or empty list."""
    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    engine_config: dict[str, dict[str, Any]] = knowledge.get("engine_config", {})
    config = engine_config.get(engine, {})
    return config.get("extra_args", [])


async def set_engine_config(
    db: AsyncSession,
    project_id: uuid.UUID,
    engine: str,
    extra_args: list[str],
) -> dict[str, Any]:
    """Save extra CLI args for *engine* on a project."""
    project = await get_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    knowledge = copy.deepcopy(project.knowledge) if project.knowledge else {}
    engine_config = knowledge.get("engine_config", {})
    engine_config[engine] = {"extra_args": extra_args}
    knowledge["engine_config"] = engine_config

    project.knowledge = knowledge
    await db.commit()
    await db.refresh(project)

    return {"engine": engine, "extra_args": extra_args}
