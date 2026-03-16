"""Knowledge base and agent charter endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.knowledge import CharterDocument, KnowledgeUpdate
from codehive.core.knowledge import (
    get_charter,
    get_knowledge,
    set_charter,
    update_knowledge,
)
from codehive.core.knowledge_analyzer import analyze_codebase, populate_knowledge
from codehive.core.project import ProjectNotFoundError, get_project

router = APIRouter(prefix="/api/projects", tags=["knowledge"])


@router.get("/{project_id}/knowledge")
async def get_knowledge_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_knowledge(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.patch("/{project_id}/knowledge")
async def update_knowledge_endpoint(
    project_id: uuid.UUID,
    body: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        # Nothing to update, just return current
        try:
            return await get_knowledge(db, project_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await update_knowledge(db, project_id, updates)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/knowledge/auto-populate")
async def auto_populate_knowledge_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        project = await get_project(db, project_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    project_path = project.path
    if not project_path:
        raise HTTPException(
            status_code=400,
            detail="Project has no path configured; cannot analyze codebase",
        )

    analysis = await analyze_codebase(project_path)
    try:
        updated = await populate_knowledge(db, project_id, analysis)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"analysis": analysis, "knowledge": updated}


@router.get("/{project_id}/charter")
async def get_charter_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_charter(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.put("/{project_id}/charter")
async def put_charter_endpoint(
    project_id: uuid.UUID,
    body: CharterDocument,
    db: AsyncSession = Depends(get_db),
) -> dict:
    charter_data = body.model_dump()
    try:
        return await set_charter(db, project_id, charter_data)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
