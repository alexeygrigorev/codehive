"""CRUD endpoints for agent roles."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.role import RoleCreate, RoleRead, RoleUpdate
from codehive.core.roles import (
    RoleNotFoundError,
    list_builtin_roles,
    load_role,
    merge_role,
)
from codehive.db.models import CustomRole, Project

router = APIRouter(prefix="/api/roles", tags=["roles"])
project_roles_router = APIRouter(prefix="/api/projects", tags=["roles"])


def _role_to_read(role_def, *, is_builtin: bool) -> RoleRead:
    """Convert a RoleDefinition to a RoleRead schema."""
    return RoleRead(
        name=role_def.name,
        display_name=role_def.display_name,
        description=role_def.description,
        responsibilities=role_def.responsibilities,
        allowed_tools=role_def.allowed_tools,
        denied_tools=role_def.denied_tools,
        coding_rules=role_def.coding_rules,
        system_prompt_extra=role_def.system_prompt_extra,
        is_builtin=is_builtin,
    )


async def _get_custom_roles_dict(db: AsyncSession) -> dict[str, dict]:
    """Load all custom roles from DB into a dict keyed by name."""
    result = await db.execute(select(CustomRole))
    rows = result.scalars().all()
    return {row.name: {**row.definition, "name": row.name} for row in rows}


@router.get("", response_model=list[RoleRead])
async def list_roles_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[RoleRead]:
    """Return all available roles (built-in + custom)."""
    roles: list[RoleRead] = []

    # Built-in roles
    for name in list_builtin_roles():
        try:
            role_def = load_role(name)
            roles.append(_role_to_read(role_def, is_builtin=True))
        except RoleNotFoundError:
            pass

    # Custom roles from DB
    custom = await _get_custom_roles_dict(db)
    for name, data in custom.items():
        try:
            from codehive.core.roles import RoleDefinition

            role_def = RoleDefinition(**data)
            roles.append(_role_to_read(role_def, is_builtin=False))
        except Exception:
            pass

    return roles


@router.get("/{role_name}", response_model=RoleRead)
async def get_role_endpoint(
    role_name: str,
    db: AsyncSession = Depends(get_db),
) -> RoleRead:
    """Return a single role definition."""
    # Check built-in
    builtin_names = set(list_builtin_roles())
    if role_name in builtin_names:
        role_def = load_role(role_name)
        return _role_to_read(role_def, is_builtin=True)

    # Check custom
    row = await db.get(CustomRole, role_name)
    if row is not None:
        from codehive.core.roles import RoleDefinition

        role_def = RoleDefinition(**{**row.definition, "name": row.name})
        return _role_to_read(role_def, is_builtin=False)

    raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")


@router.post("", response_model=RoleRead, status_code=201)
async def create_role_endpoint(
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
) -> RoleRead:
    """Create a custom role. Rejects duplicate names (including built-in) with 409."""
    # Check conflicts with built-in
    if body.name in set(list_builtin_roles()):
        raise HTTPException(
            status_code=409,
            detail=f"Role '{body.name}' already exists as a built-in role",
        )

    # Check conflicts with existing custom
    existing = await db.get(CustomRole, body.name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Custom role '{body.name}' already exists",
        )

    definition = body.model_dump(exclude={"name"})
    row = CustomRole(
        name=body.name,
        definition=definition,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    from codehive.core.roles import RoleDefinition

    role_def = RoleDefinition(**{**row.definition, "name": row.name})
    return _role_to_read(role_def, is_builtin=False)


@router.put("/{role_name}", response_model=RoleRead)
async def update_role_endpoint(
    role_name: str,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
) -> RoleRead:
    """Update a custom role. Rejects updates to built-in roles with 403."""
    if role_name in set(list_builtin_roles()):
        raise HTTPException(status_code=403, detail="Cannot modify built-in roles")

    row = await db.get(CustomRole, role_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Custom role '{role_name}' not found")

    updates = body.model_dump(exclude_unset=True)
    new_def = {**row.definition, **updates}
    row.definition = new_def
    await db.commit()
    await db.refresh(row)

    from codehive.core.roles import RoleDefinition

    role_def = RoleDefinition(**{**row.definition, "name": row.name})
    return _role_to_read(role_def, is_builtin=False)


@router.delete("/{role_name}", status_code=204)
async def delete_role_endpoint(
    role_name: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a custom role. Rejects deletion of built-in roles with 403."""
    if role_name in set(list_builtin_roles()):
        raise HTTPException(status_code=403, detail="Cannot delete built-in roles")

    row = await db.get(CustomRole, role_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Custom role '{role_name}' not found")

    await db.delete(row)
    await db.commit()


@project_roles_router.get(
    "/{project_id}/roles/{role_name}",
    response_model=RoleRead,
    tags=["roles"],
)
async def get_project_role_endpoint(
    project_id: uuid.UUID,
    role_name: str,
    db: AsyncSession = Depends(get_db),
) -> RoleRead:
    """Return the resolved role for a project (global merged with project overrides)."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load the base role (built-in or custom)
    custom = await _get_custom_roles_dict(db)
    try:
        role_def = load_role(role_name, custom_roles=custom)
    except RoleNotFoundError:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

    # Check for project-level overrides
    knowledge = project.knowledge or {}
    role_overrides = knowledge.get("role_overrides", {})
    overrides = role_overrides.get(role_name, {})

    is_builtin = role_name in set(list_builtin_roles())

    if overrides:
        role_def = merge_role(role_def, overrides)

    return _role_to_read(role_def, is_builtin=is_builtin)
