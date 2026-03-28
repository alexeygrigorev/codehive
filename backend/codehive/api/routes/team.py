"""CRUD endpoints for agent profiles (project team)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.team import AgentProfileCreate, AgentProfileRead, AgentProfileUpdate
from codehive.db.models import AgentProfile, Project

router = APIRouter(prefix="/api/projects/{project_id}/team", tags=["team"])


async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[AgentProfileRead])
async def list_team(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[AgentProfileRead]:
    """List all agent profiles for a project."""
    await _get_project_or_404(db, project_id)
    result = await db.execute(
        select(AgentProfile)
        .where(AgentProfile.project_id == project_id)
        .order_by(AgentProfile.created_at)
    )
    profiles = list(result.scalars().all())
    return [AgentProfileRead.model_validate(p) for p in profiles]


@router.post("", response_model=AgentProfileRead, status_code=201)
async def add_team_member(
    project_id: uuid.UUID,
    body: AgentProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentProfileRead:
    """Add a new agent profile to a project's team."""
    await _get_project_or_404(db, project_id)

    avatar_seed = body.avatar_seed or f"{body.name}-{project_id}"
    profile = AgentProfile(
        project_id=project_id,
        name=body.name,
        role=body.role,
        avatar_seed=avatar_seed,
        personality=body.personality,
        system_prompt_modifier=body.system_prompt_modifier,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return AgentProfileRead.model_validate(profile)


@router.patch("/{agent_id}", response_model=AgentProfileRead)
async def update_team_member(
    project_id: uuid.UUID,
    agent_id: uuid.UUID,
    body: AgentProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentProfileRead:
    """Update an agent profile."""
    await _get_project_or_404(db, project_id)
    profile = await db.get(AgentProfile, agent_id)
    if profile is None or profile.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    fields = body.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    return AgentProfileRead.model_validate(profile)


@router.delete("/{agent_id}", status_code=204)
async def remove_team_member(
    project_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an agent profile from a project's team."""
    await _get_project_or_404(db, project_id)
    profile = await db.get(AgentProfile, agent_id)
    if profile is None or profile.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    await db.delete(profile)
    await db.commit()
