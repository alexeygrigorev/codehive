"""Tests for the project archetypes system: loading, validation, application, API."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import yaml

from codehive.db.models import Base
from codehive.core.archetypes import (
    ArchetypeDefinition,
    ArchetypeNotFoundError,
    apply_archetype_to_knowledge,
    list_builtin_archetypes,
    load_archetype,
    reset_builtin_dir,
    set_builtin_dir,
)
from codehive.core.roles import list_builtin_roles


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_builtin_dir():
    """Ensure the builtin dir is reset after each test."""
    yield
    reset_builtin_dir()


# ---------------------------------------------------------------------------
# Unit: Archetype Loading and Validation
# ---------------------------------------------------------------------------


class TestArchetypeLoading:
    def test_list_builtin_archetypes(self):
        """list_builtin_archetypes returns the four expected names, sorted."""
        names = list_builtin_archetypes()
        assert names == [
            "code_maintenance",
            "research",
            "software_development",
            "technical_operations",
        ]

    def test_load_software_development(self):
        """Load software_development archetype, verify all fields populated."""
        arch = load_archetype("software_development")
        assert isinstance(arch, ArchetypeDefinition)
        assert arch.name == "software_development"
        assert arch.display_name == "Software Development"
        assert arch.description
        assert arch.roles == ["product_manager", "developer", "tester"]
        assert len(arch.workflow) > 0
        assert isinstance(arch.default_settings, dict)
        assert isinstance(arch.tech_stack, list)

    def test_load_research(self):
        """Load research archetype, verify all fields populated."""
        arch = load_archetype("research")
        assert arch.name == "research"
        assert arch.display_name == "Research"
        assert arch.description
        assert len(arch.roles) > 0
        assert len(arch.workflow) > 0

    def test_load_technical_operations(self):
        """Load technical_operations archetype, verify all fields populated."""
        arch = load_archetype("technical_operations")
        assert arch.name == "technical_operations"
        assert arch.display_name == "Technical Operations"
        assert arch.description
        assert len(arch.roles) > 0

    def test_load_code_maintenance(self):
        """Load code_maintenance archetype, verify all fields populated."""
        arch = load_archetype("code_maintenance")
        assert arch.name == "code_maintenance"
        assert arch.display_name == "Code Maintenance"
        assert arch.description
        assert len(arch.roles) > 0

    def test_load_nonexistent_raises(self):
        """Loading a nonexistent archetype raises ArchetypeNotFoundError."""
        with pytest.raises(ArchetypeNotFoundError, match="not found"):
            load_archetype("nonexistent")

    def test_missing_required_fields_raises(self, tmp_path: Path):
        """Archetype YAML with missing required fields raises ValidationError."""
        set_builtin_dir(tmp_path)
        # name is empty string -> should fail validation
        (tmp_path / "bad.yaml").write_text(yaml.dump({"name": ""}))
        with pytest.raises(Exception):
            load_archetype("bad")

    def test_all_role_references_valid(self):
        """Every role name in each built-in archetype exists as a built-in role."""
        valid_roles = set(list_builtin_roles())
        for name in list_builtin_archetypes():
            arch = load_archetype(name)
            for role in arch.roles:
                assert role in valid_roles, f"Archetype '{name}' references unknown role '{role}'"


# ---------------------------------------------------------------------------
# Unit: Archetype Application to Project Knowledge
# ---------------------------------------------------------------------------


class TestArchetypeApplication:
    def test_apply_archetype_populates_knowledge(self):
        """apply_archetype_to_knowledge populates archetype_roles and archetype_settings."""
        result = apply_archetype_to_knowledge({}, "software_development")
        assert result["archetype_roles"] == ["product_manager", "developer", "tester"]
        assert result["archetype_settings"]["auto_start_tasks"] is True
        assert result["archetype_settings"]["require_approval_destructive"] is True

    def test_apply_preserves_existing_keys(self):
        """Applying archetype to existing knowledge dict preserves other keys."""
        existing = {"some_key": "some_value", "other": 42}
        result = apply_archetype_to_knowledge(existing, "software_development")
        assert result["some_key"] == "some_value"
        assert result["other"] == 42
        assert "archetype_roles" in result

    def test_apply_none_returns_unchanged(self):
        """Applying with archetype=None returns knowledge unchanged."""
        knowledge = {"existing": "data"}
        result = apply_archetype_to_knowledge(knowledge, None)
        assert result == {"existing": "data"}

    def test_apply_nonexistent_raises(self):
        """Applying a nonexistent archetype raises ArchetypeNotFoundError."""
        with pytest.raises(ArchetypeNotFoundError):
            apply_archetype_to_knowledge({}, "nonexistent")


# ---------------------------------------------------------------------------
# Integration: API Endpoints
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create tables in an in-memory SQLite DB and yield an async session."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_session):
    """Create an async test client with the DB session overridden."""
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from codehive.api.app import create_app
    from codehive.api.deps import get_db

    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user and include auth headers
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest_asyncio.fixture
async def workspace_id(db_session):
    """Create a workspace and return its ID for project creation tests."""
    from datetime import datetime, timezone

    from codehive.db.models import Workspace

    ws = Workspace(
        id=uuid.uuid4(),
        name="test-workspace",
        root_path="/tmp/test",
        settings={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    return ws.id


@pytest_asyncio.fixture
async def workspace_id_member(workspace_id, async_client, db_session):
    """Ensure the test user is an owner of the workspace."""
    from tests.conftest import ensure_workspace_membership

    await ensure_workspace_membership(db_session, workspace_id)
    return workspace_id


class TestArchetypesAPI:
    @pytest.mark.asyncio
    async def test_list_archetypes(self, async_client):
        """GET /api/archetypes returns 200 with all four built-in archetypes."""
        resp = await async_client.get("/api/archetypes")
        assert resp.status_code == 200
        data = resp.json()
        names = [a["name"] for a in data]
        assert len(data) >= 4
        assert "software_development" in names
        assert "research" in names
        assert "technical_operations" in names
        assert "code_maintenance" in names
        # Verify fields present
        for item in data:
            assert "name" in item
            assert "display_name" in item
            assert "description" in item
            assert "roles" in item
            assert "workflow" in item

    @pytest.mark.asyncio
    async def test_get_research_archetype(self, async_client):
        """GET /api/archetypes/research returns 200 with correct data."""
        resp = await async_client.get("/api/archetypes/research")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "research"
        assert data["display_name"] == "Research"
        assert data["is_builtin"] is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_archetype(self, async_client):
        """GET /api/archetypes/nonexistent returns 404."""
        resp = await async_client.get("/api/archetypes/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_project_with_valid_archetype(self, async_client, workspace_id_member):
        """POST /api/projects with valid archetype populates knowledge correctly."""
        body = {
            "workspace_id": str(workspace_id_member),
            "name": "test-project",
            "archetype": "software_development",
        }
        resp = await async_client.post("/api/projects", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["archetype"] == "software_development"
        assert data["knowledge"]["archetype_roles"] == [
            "product_manager",
            "developer",
            "tester",
        ]
        assert data["knowledge"]["archetype_settings"]["auto_start_tasks"] is True

    @pytest.mark.asyncio
    async def test_create_project_without_archetype(self, async_client, workspace_id_member):
        """POST /api/projects without archetype works as before."""
        body = {
            "workspace_id": str(workspace_id_member),
            "name": "no-archetype-project",
        }
        resp = await async_client.post("/api/projects", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["archetype"] is None
        assert "archetype_roles" not in data["knowledge"]

    @pytest.mark.asyncio
    async def test_create_project_with_invalid_archetype(self, async_client, workspace_id_member):
        """POST /api/projects with invalid archetype returns 400."""
        body = {
            "workspace_id": str(workspace_id_member),
            "name": "bad-archetype-project",
            "archetype": "nonexistent",
        }
        resp = await async_client.post("/api/projects", json=body)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_clone_archetype(self, async_client):
        """POST /api/archetypes/software_development/clone returns 201."""
        body = {
            "name": "my_custom_dev",
            "display_name": "My Custom Dev",
            "tech_stack": ["python", "fastapi"],
        }
        resp = await async_client.post("/api/archetypes/software_development/clone", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my_custom_dev"
        assert data["display_name"] == "My Custom Dev"
        assert data["is_builtin"] is False
        # Should inherit roles from source
        assert data["roles"] == ["product_manager", "developer", "tester"]
        # Should have overridden tech_stack
        assert data["tech_stack"] == ["python", "fastapi"]

    @pytest.mark.asyncio
    async def test_clone_with_builtin_name_returns_409(self, async_client):
        """POST clone with duplicate built-in name returns 409."""
        body = {"name": "software_development"}
        resp = await async_client.post("/api/archetypes/software_development/clone", json=body)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_archetypes_includes_cloned(self, async_client):
        """GET /api/archetypes after cloning includes the custom archetype."""
        # Clone first
        body = {"name": "cloned_arch", "display_name": "Cloned"}
        resp = await async_client.post("/api/archetypes/research/clone", json=body)
        assert resp.status_code == 201

        # List and verify
        resp = await async_client.get("/api/archetypes")
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert "cloned_arch" in names
        assert "software_development" in names
