"""Project business logic (DB queries)."""

import os
import subprocess
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.archetypes import (
    ArchetypeNotFoundError,
    apply_archetype_to_knowledge,
)
from codehive.db.models import Project


class InvalidArchetypeError(Exception):
    """Raised when an invalid archetype name is provided."""


class ProjectNotFoundError(Exception):
    """Raised when a project is not found by ID."""


class ProjectHasDependentsError(Exception):
    """Raised when a project cannot be deleted because it has associated sessions or issues."""


async def create_project(
    session: AsyncSession,
    *,
    name: str,
    path: str | None = None,
    description: str | None = None,
    archetype: str | None = None,
) -> Project:
    """Create a new project.

    If archetype is set, applies archetype roles and settings to the project knowledge.
    Raises InvalidArchetypeError if the archetype name is not valid.
    """
    knowledge: dict = {}
    if archetype is not None:
        try:
            knowledge = apply_archetype_to_knowledge(knowledge, archetype)
        except ArchetypeNotFoundError:
            raise InvalidArchetypeError(f"Archetype '{archetype}' not found")

    project = Project(
        name=name,
        path=path,
        description=description,
        archetype=archetype,
        knowledge=knowledge,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> list[Project]:
    """Return all projects."""
    result = await session.execute(select(Project))
    return list(result.scalars().all())


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """Return a project by ID, or None if not found."""
    return await session.get(Project, project_id)


async def update_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    **fields: str | None,
) -> Project:
    """Update specific fields on a project. Raises ProjectNotFoundError if not found."""
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    for key, value in fields.items():
        setattr(project, key, value)

    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project_id: uuid.UUID) -> None:
    """Delete a project. Raises ProjectNotFoundError if not found.

    Raises ProjectHasDependentsError if the project has associated sessions or issues.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    # Check for dependent sessions/issues (lazy-load them)
    await session.refresh(project, attribute_names=["sessions", "issues"])
    if project.sessions or project.issues:
        raise ProjectHasDependentsError(f"Project {project_id} has associated sessions or issues")

    await session.delete(project)
    await session.commit()


def ensure_directory_with_git(path: str, *, git_init: bool = False) -> None:
    """Create the directory if needed, and optionally run ``git init``.

    * Always creates the directory (``os.makedirs`` with ``exist_ok=True``).
    * When *git_init* is ``True`` and ``.git/`` does not already exist, runs
      ``git init`` inside the directory.
    """
    resolved = os.path.normpath(os.path.expanduser(path))
    os.makedirs(resolved, exist_ok=True)
    if git_init and not os.path.isdir(os.path.join(resolved, ".git")):
        subprocess.run(["git", "init"], cwd=resolved, check=True, capture_output=True)


def normalize_path(path: str) -> str:
    """Normalize a filesystem path: resolve to absolute, strip trailing slashes."""
    # os.path.normpath handles trailing slashes and redundant separators
    return os.path.normpath(os.path.abspath(path))


async def get_project_by_path(
    session: AsyncSession,
    path: str,
) -> Project | None:
    """Return a project matching the normalized absolute path, or None."""
    normalized = normalize_path(path)
    result = await session.execute(select(Project).where(Project.path == normalized))
    return result.scalar_one_or_none()


async def get_or_create_project_by_path(
    session: AsyncSession,
    path: str,
) -> tuple[Project, bool]:
    """Look up a project by path; create it if it doesn't exist.

    Returns (project, created) where created is True if a new project was made.
    The project name is derived from the path basename.
    """
    normalized = normalize_path(path)
    existing = await get_project_by_path(session, normalized)
    if existing is not None:
        return existing, False

    name = os.path.basename(normalized)
    project = Project(
        name=name,
        path=normalized,
        knowledge={},
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project, True
