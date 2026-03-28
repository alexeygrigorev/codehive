"""CRUD endpoints for projects."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from codehive.core.context_files import read_context_file, scan_context_files
from codehive.core.project import (
    InvalidArchetypeError,
    ProjectNotFoundError,
    archive_project,
    create_project,
    delete_project,
    ensure_directory_with_git,
    get_or_create_project_by_path,
    get_project,
    get_project_by_path,
    list_archived_projects,
    unarchive_project,
    update_project,
)
from codehive.db.models import Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project_endpoint(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    # Handle directory creation and optional git init
    if body.path:
        ensure_directory_with_git(body.path, git_init=body.git_init)

    try:
        project = await create_project(
            db,
            name=body.name,
            path=body.path,
            description=body.description,
            archetype=body.archetype,
        )
    except InvalidArchetypeError:
        raise HTTPException(status_code=400, detail=f"Invalid archetype: '{body.archetype}'")
    return ProjectRead.model_validate(project)


@router.get("/by-path", response_model=ProjectRead)
async def get_project_by_path_endpoint(
    path: str = Query(..., description="Absolute filesystem path"),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """Look up a project by its filesystem path. Returns 404 if not found."""
    project = await get_project_by_path(db, path)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


class ProjectByPathRequest(BaseModel):
    """Request body for POST /api/projects/by-path."""

    path: str


@router.post("/by-path", response_model=ProjectRead)
async def create_project_by_path_endpoint(
    body: ProjectByPathRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """Get or create a project by filesystem path."""
    project, created = await get_or_create_project_by_path(db, body.path)
    response.status_code = 201 if created else 200
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects_endpoint(
    include_archived: bool = Query(False, description="Include archived projects"),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    if include_archived:
        result = await db.execute(select(Project))
    else:
        result = await db.execute(select(Project).where(Project.archived_at.is_(None)))
    projects = list(result.scalars().all())
    return [ProjectRead.model_validate(p) for p in projects]


@router.get("/archived", response_model=list[ProjectRead])
async def list_archived_projects_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    """Return only archived projects."""
    projects = await list_archived_projects(db)
    return [ProjectRead.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    project = await get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project_endpoint(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        project = await update_project(db, project_id, **fields)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_project(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/archive", response_model=ProjectRead)
async def archive_project_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    try:
        project = await archive_project(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.post("/{project_id}/unarchive", response_model=ProjectRead)
async def unarchive_project_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    try:
        project = await unarchive_project(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


# ---------------------------------------------------------------------------
# Context files endpoints
# ---------------------------------------------------------------------------


class ContextFileEntry(BaseModel):
    path: str
    size: int


class ContextFileContent(BaseModel):
    path: str
    content: str


@router.get(
    "/{project_id}/context-files",
    response_model=list[ContextFileEntry],
)
async def list_context_files_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ContextFileEntry]:
    """Return detected context files for a project."""
    project = await get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.path:
        return []

    files = scan_context_files(project.path)
    return [ContextFileEntry(**f) for f in files]


@router.get(
    "/{project_id}/context-files/{file_path:path}",
    response_model=ContextFileContent,
)
async def read_context_file_endpoint(
    project_id: uuid.UUID,
    file_path: str,
    db: AsyncSession = Depends(get_db),
) -> ContextFileContent:
    """Return the content of a single context file."""
    project = await get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.path:
        raise HTTPException(status_code=404, detail="Project has no path")

    try:
        content = read_context_file(project.path, file_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Context file not found")

    return ContextFileContent(path=file_path, content=content)
