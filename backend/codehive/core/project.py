"""Project business logic (DB queries)."""

import os
import subprocess
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
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
    """Raised when a project cannot be deleted because it has associated sessions or issues.

    .. deprecated:: Kept for backward compatibility but no longer raised by delete_project.
    """


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
    await session.flush()

    # Generate default team of agent profiles
    from codehive.core.team import generate_default_team

    await generate_default_team(session, project.id)

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
    """Delete a project and all related data via DB-level cascade.

    Raises ProjectNotFoundError if not found.
    Uses a raw DELETE statement to avoid ORM lazy-loading issues with
    deep relationship cascades; the DB-level ON DELETE CASCADE handles cleanup.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    # Use raw DELETE so DB-level ON DELETE CASCADE handles all children
    # without requiring ORM to eager-load entire relationship trees.
    await session.execute(delete(Project).where(Project.id == project_id))
    # Expunge the stale ORM object from the identity map
    session.expunge(project)
    await session.commit()


async def archive_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    """Set archived_at on a project. Raises ProjectNotFoundError if not found."""
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    if project.archived_at is None:
        project.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await session.commit()
    await session.refresh(project)
    return project


async def unarchive_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    """Clear archived_at on a project. Raises ProjectNotFoundError if not found."""
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    project.archived_at = None

    await session.commit()
    await session.refresh(project)
    return project


async def list_archived_projects(session: AsyncSession) -> list[Project]:
    """Return only archived projects."""
    result = await session.execute(select(Project).where(Project.archived_at.isnot(None)))
    return list(result.scalars().all())


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
