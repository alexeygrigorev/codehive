"""CRUD endpoints for project archetypes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.archetype import ArchetypeCloneRequest, ArchetypeRead
from codehive.core.archetypes import (
    ArchetypeDefinition,
    ArchetypeNotFoundError,
    list_builtin_archetypes,
    load_archetype,
)
from codehive.db.models import CustomArchetype

router = APIRouter(prefix="/api/archetypes", tags=["archetypes"])


def _archetype_to_read(archetype_def: ArchetypeDefinition, *, is_builtin: bool) -> ArchetypeRead:
    """Convert an ArchetypeDefinition to an ArchetypeRead schema."""
    return ArchetypeRead(
        name=archetype_def.name,
        display_name=archetype_def.display_name,
        description=archetype_def.description,
        roles=archetype_def.roles,
        workflow=archetype_def.workflow,
        default_settings=archetype_def.default_settings,
        tech_stack=archetype_def.tech_stack,
        is_builtin=is_builtin,
    )


@router.get("", response_model=list[ArchetypeRead])
async def list_archetypes_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[ArchetypeRead]:
    """Return all available archetypes (built-in + custom)."""
    archetypes: list[ArchetypeRead] = []

    # Built-in archetypes
    for name in list_builtin_archetypes():
        try:
            arch_def = load_archetype(name)
            archetypes.append(_archetype_to_read(arch_def, is_builtin=True))
        except ArchetypeNotFoundError:
            pass

    # Custom archetypes from DB
    result = await db.execute(select(CustomArchetype))
    rows = result.scalars().all()
    for row in rows:
        try:
            arch_def = ArchetypeDefinition(**{**row.definition, "name": row.name})
            archetypes.append(_archetype_to_read(arch_def, is_builtin=False))
        except Exception:
            pass

    return archetypes


@router.get("/{archetype_name}", response_model=ArchetypeRead)
async def get_archetype_endpoint(
    archetype_name: str,
    db: AsyncSession = Depends(get_db),
) -> ArchetypeRead:
    """Return a single archetype definition."""
    # Check built-in
    builtin_names = set(list_builtin_archetypes())
    if archetype_name in builtin_names:
        arch_def = load_archetype(archetype_name)
        return _archetype_to_read(arch_def, is_builtin=True)

    # Check custom
    row = await db.get(CustomArchetype, archetype_name)
    if row is not None:
        arch_def = ArchetypeDefinition(**{**row.definition, "name": row.name})
        return _archetype_to_read(arch_def, is_builtin=False)

    raise HTTPException(status_code=404, detail=f"Archetype '{archetype_name}' not found")


@router.post("/{archetype_name}/clone", response_model=ArchetypeRead, status_code=201)
async def clone_archetype_endpoint(
    archetype_name: str,
    body: ArchetypeCloneRequest,
    db: AsyncSession = Depends(get_db),
) -> ArchetypeRead:
    """Clone a built-in archetype with overrides, storing it as a custom archetype."""
    # Load the source archetype
    builtin_names = set(list_builtin_archetypes())
    source: ArchetypeDefinition | None = None

    if archetype_name in builtin_names:
        source = load_archetype(archetype_name)
    else:
        row = await db.get(CustomArchetype, archetype_name)
        if row is not None:
            source = ArchetypeDefinition(**{**row.definition, "name": row.name})

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=f"Archetype '{archetype_name}' not found",
        )

    # Check that the new name doesn't conflict with a built-in
    if body.name in builtin_names:
        raise HTTPException(
            status_code=409,
            detail=f"Archetype '{body.name}' already exists as a built-in archetype",
        )

    # Check that the new name doesn't conflict with an existing custom archetype
    existing = await db.get(CustomArchetype, body.name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Custom archetype '{body.name}' already exists",
        )

    # Build the cloned definition with overrides
    cloned_data = source.model_dump()
    cloned_data["name"] = body.name
    if body.display_name is not None:
        cloned_data["display_name"] = body.display_name
    if body.description is not None:
        cloned_data["description"] = body.description
    if body.roles is not None:
        cloned_data["roles"] = body.roles
    if body.workflow is not None:
        cloned_data["workflow"] = body.workflow
    if body.default_settings is not None:
        cloned_data["default_settings"] = body.default_settings
    if body.tech_stack is not None:
        cloned_data["tech_stack"] = body.tech_stack

    arch_def = ArchetypeDefinition(**cloned_data)

    # Store in DB (definition excludes name since name is the PK)
    definition = arch_def.model_dump(exclude={"name"})
    custom_row = CustomArchetype(
        name=body.name,
        definition=definition,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(custom_row)
    await db.commit()
    await db.refresh(custom_row)

    return _archetype_to_read(arch_def, is_builtin=False)
