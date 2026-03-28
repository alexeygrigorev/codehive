"""Prompt template and engine configuration endpoints for projects."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.project import ProjectNotFoundError, get_project
from codehive.core.roles import BUILTIN_ROLES
from codehive.core.spawn_config import (
    delete_prompt_template,
    get_engine_config,
    get_prompt_templates,
    set_engine_config,
    set_prompt_template,
)

router = APIRouter(prefix="/api/projects", tags=["spawn-config"])

VALID_ROLES = set(BUILTIN_ROLES.keys())


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PromptTemplateUpdate(BaseModel):
    system_prompt: str


class PromptTemplateRead(BaseModel):
    role: str
    display_name: str
    system_prompt: str
    is_custom: bool


class EngineConfigUpdate(BaseModel):
    extra_args: list[str]


class EngineConfigRead(BaseModel):
    engine: str
    extra_args: list[str]


# ---------------------------------------------------------------------------
# Prompt template endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/prompt-templates",
    response_model=list[PromptTemplateRead],
)
async def get_prompt_templates_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[PromptTemplateRead]:
    project = await get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    templates = get_prompt_templates(project)
    return [PromptTemplateRead(**t) for t in templates]


@router.put("/{project_id}/prompt-templates/{role}")
async def put_prompt_template_endpoint(
    project_id: uuid.UUID,
    role: str,
    body: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
) -> PromptTemplateRead:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid role: '{role}'")

    try:
        result = await set_prompt_template(db, project_id, role, body.system_prompt)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    return PromptTemplateRead(**result)


@router.delete("/{project_id}/prompt-templates/{role}")
async def delete_prompt_template_endpoint(
    project_id: uuid.UUID,
    role: str,
    db: AsyncSession = Depends(get_db),
) -> PromptTemplateRead:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid role: '{role}'")

    try:
        result = await delete_prompt_template(db, project_id, role)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    return PromptTemplateRead(**result)


# ---------------------------------------------------------------------------
# Engine config endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/engine-config",
    response_model=list[EngineConfigRead],
)
async def get_engine_config_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[EngineConfigRead]:
    project = await get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    configs = get_engine_config(project)
    return [EngineConfigRead(**c) for c in configs]


@router.put("/{project_id}/engine-config/{engine}")
async def put_engine_config_endpoint(
    project_id: uuid.UUID,
    engine: str,
    body: EngineConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> EngineConfigRead:
    try:
        result = await set_engine_config(db, project_id, engine, body.extra_args)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    return EngineConfigRead(**result)
