"""Project business logic (DB queries)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.archetypes import (
    ArchetypeNotFoundError,
    apply_archetype_to_knowledge,
)
from codehive.db.models import Project, Workspace


class InvalidArchetypeError(Exception):
    """Raised when an invalid archetype name is provided."""


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace_id does not exist."""


class ProjectNotFoundError(Exception):
    """Raised when a project is not found by ID."""


class ProjectHasDependentsError(Exception):
    """Raised when a project cannot be deleted because it has associated sessions or issues."""


async def create_project(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    name: str,
    path: str | None = None,
    description: str | None = None,
    archetype: str | None = None,
) -> Project:
    """Create a new project. Raises WorkspaceNotFoundError if workspace doesn't exist.

    If archetype is set, applies archetype roles and settings to the project knowledge.
    Raises InvalidArchetypeError if the archetype name is not valid.
    """
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

    knowledge: dict = {}
    if archetype is not None:
        try:
            knowledge = apply_archetype_to_knowledge(knowledge, archetype)
        except ArchetypeNotFoundError:
            raise InvalidArchetypeError(f"Archetype '{archetype}' not found")

    project = Project(
        workspace_id=workspace_id,
        name=name,
        path=path,
        description=description,
        archetype=archetype,
        knowledge=knowledge,
        created_at=datetime.now(timezone.utc),
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
