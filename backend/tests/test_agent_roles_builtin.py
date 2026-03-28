"""Tests for issue #138: Built-in agent roles (PM, SWE, QA, OnCall).

Covers:
- BUILTIN_ROLES constant validation
- Role-based pipeline transition enforcement
- Role seeding into DB
- Session API with role field
- Pipeline transition API with actor_session_id
- Roles API (list, get, patch)
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.roles import (
    BUILTIN_ROLES,
    is_valid_role,
    seed_builtin_roles,
)
from codehive.core.task_queue import (
    InvalidPipelineTransitionError,
    RoleNotAllowedError as TQRoleNotAllowedError,
    create_task,
    pipeline_transition,
)
from codehive.db.models import Base, CustomRole, Project
from codehive.db.models import Session as SessionModel

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
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
async def project(db_session: AsyncSession) -> Project:
    proj = Project(
        name="test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


def _make_session(
    db_session: AsyncSession, project: Project, *, role: str | None = None
) -> SessionModel:
    """Helper to create a session with a given role."""
    s = SessionModel(
        project_id=project.id,
        name=f"session-{role or 'none'}",
        engine="native",
        mode="execution",
        status="idle",
        role=role,
        config={},
        created_at=datetime.now(timezone.utc),
    )
    return s


@pytest_asyncio.fixture
async def pm_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = _make_session(db_session, project, role="pm")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def swe_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = _make_session(db_session, project, role="swe")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def qa_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = _make_session(db_session, project, role="qa")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def oncall_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = _make_session(db_session, project, role="oncall")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "roles@test.com", "username": "roleuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit: BUILTIN_ROLES constant validation
# ---------------------------------------------------------------------------


class TestBuiltinRolesConstant:
    def test_contains_exactly_four_keys(self):
        assert set(BUILTIN_ROLES.keys()) == {"pm", "swe", "qa", "oncall"}

    def test_each_role_has_required_fields(self):
        for name, role_def in BUILTIN_ROLES.items():
            assert "display_name" in role_def, f"{name} missing display_name"
            assert "system_prompt" in role_def, f"{name} missing system_prompt"
            assert "allowed_transitions" in role_def, f"{name} missing allowed_transitions"
            assert "color" in role_def, f"{name} missing color"

    def test_allowed_transitions_reference_valid_statuses(self):
        from codehive.core.task_queue import VALID_PIPELINE_STATUSES

        for name, role_def in BUILTIN_ROLES.items():
            for from_status, targets in role_def["allowed_transitions"].items():
                assert from_status in VALID_PIPELINE_STATUSES, (
                    f"{name}: invalid from_status '{from_status}'"
                )
                for to_status in targets:
                    assert to_status in VALID_PIPELINE_STATUSES, (
                        f"{name}: invalid to_status '{to_status}'"
                    )

    def test_is_valid_role(self):
        assert is_valid_role("pm") is True
        assert is_valid_role("swe") is True
        assert is_valid_role("qa") is True
        assert is_valid_role("oncall") is True
        assert is_valid_role("hacker") is False


# ---------------------------------------------------------------------------
# Unit: Role-based pipeline transition validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRoleBasedPipelineTransition:
    async def test_pm_backlog_to_grooming_succeeds(
        self, db_session: AsyncSession, pm_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        result = await pipeline_transition(
            db_session, task.id, "grooming", actor_session_id=pm_session.id
        )
        assert result.pipeline_status == "grooming"

    async def test_pm_groomed_to_implementing_raises(
        self, db_session: AsyncSession, pm_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        with pytest.raises(TQRoleNotAllowedError, match="pm.*not allowed"):
            await pipeline_transition(
                db_session, task.id, "implementing", actor_session_id=pm_session.id
            )

    async def test_swe_groomed_to_implementing_succeeds(
        self, db_session: AsyncSession, swe_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        result = await pipeline_transition(
            db_session, task.id, "implementing", actor_session_id=swe_session.id
        )
        assert result.pipeline_status == "implementing"

    async def test_swe_backlog_to_grooming_raises(
        self, db_session: AsyncSession, swe_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        with pytest.raises(TQRoleNotAllowedError, match="swe.*not allowed"):
            await pipeline_transition(
                db_session, task.id, "grooming", actor_session_id=swe_session.id
            )

    async def test_qa_testing_to_accepting_succeeds(
        self, db_session: AsyncSession, qa_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing"]:
            await pipeline_transition(db_session, task.id, s)
        result = await pipeline_transition(
            db_session, task.id, "accepting", actor_session_id=qa_session.id
        )
        assert result.pipeline_status == "accepting"

    async def test_qa_groomed_to_implementing_raises(
        self, db_session: AsyncSession, qa_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        with pytest.raises(TQRoleNotAllowedError, match="qa.*not allowed"):
            await pipeline_transition(
                db_session, task.id, "implementing", actor_session_id=qa_session.id
            )

    async def test_oncall_groomed_to_implementing_succeeds(
        self, db_session: AsyncSession, oncall_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        result = await pipeline_transition(
            db_session, task.id, "implementing", actor_session_id=oncall_session.id
        )
        assert result.pipeline_status == "implementing"

    async def test_oncall_testing_to_accepting_succeeds(
        self, db_session: AsyncSession, oncall_session: SessionModel, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing"]:
            await pipeline_transition(db_session, task.id, s)
        result = await pipeline_transition(
            db_session, task.id, "accepting", actor_session_id=oncall_session.id
        )
        assert result.pipeline_status == "accepting"

    async def test_null_role_any_transition_succeeds(
        self, db_session: AsyncSession, session: SessionModel
    ):
        """Session with role=None can perform any valid graph transition (backward compat)."""
        assert session.role is None
        task = await create_task(db_session, session_id=session.id, title="t")
        result = await pipeline_transition(
            db_session, task.id, "grooming", actor_session_id=session.id
        )
        assert result.pipeline_status == "grooming"

    async def test_invalid_graph_transition_even_with_role(
        self, db_session: AsyncSession, pm_session: SessionModel, session: SessionModel
    ):
        """Graph validation still applies -- PM cannot skip backlog -> done."""
        task = await create_task(db_session, session_id=session.id, title="t")
        with pytest.raises(InvalidPipelineTransitionError):
            await pipeline_transition(db_session, task.id, "done", actor_session_id=pm_session.id)

    async def test_actor_logged_with_role_info(
        self, db_session: AsyncSession, pm_session: SessionModel, session: SessionModel
    ):
        """When actor_session_id is provided, log records role:session:<uuid>."""
        from codehive.core.task_queue import get_pipeline_log

        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming", actor_session_id=pm_session.id)
        logs = await get_pipeline_log(db_session, task.id)
        assert len(logs) == 1
        assert logs[0].actor == f"pm:session:{pm_session.id}"


# ---------------------------------------------------------------------------
# Unit: Role seeding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRoleSeeding:
    async def test_seed_creates_four_roles(self, db_session: AsyncSession):
        count = await seed_builtin_roles(db_session)
        assert count == 4
        for name in ["pm", "swe", "qa", "oncall"]:
            row = await db_session.get(CustomRole, name)
            assert row is not None
            assert row.definition.get("is_builtin") is True

    async def test_seed_idempotent(self, db_session: AsyncSession):
        count1 = await seed_builtin_roles(db_session)
        assert count1 == 4
        count2 = await seed_builtin_roles(db_session)
        assert count2 == 0

    async def test_seed_preserves_user_edits(self, db_session: AsyncSession):
        # First seed
        await seed_builtin_roles(db_session)
        # User edits the PM system_prompt
        row = await db_session.get(CustomRole, "pm")
        new_def = {**row.definition, "system_prompt": "Custom PM prompt"}
        row.definition = new_def
        await db_session.commit()

        # Seed again -- should NOT overwrite
        await seed_builtin_roles(db_session)
        await db_session.refresh(row)
        assert row.definition["system_prompt"] == "Custom PM prompt"


# ---------------------------------------------------------------------------
# Integration: Session API with role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSessionAPIWithRole:
    async def test_create_session_with_pm_role(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={"name": "pm-sess", "engine": "native", "mode": "execution", "role": "pm"},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "pm"

    async def test_create_session_with_swe_role(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={"name": "swe-sess", "engine": "native", "mode": "execution", "role": "swe"},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "swe"

    async def test_create_session_with_null_role(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={"name": "no-role", "engine": "native", "mode": "execution", "role": None},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] is None

    async def test_create_session_invalid_role_400(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={"name": "hacker-sess", "engine": "native", "mode": "execution", "role": "hacker"},
        )
        assert resp.status_code == 400
        assert "hacker" in resp.json()["detail"]

    async def test_get_session_includes_role(self, client: AsyncClient, project: Project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={"name": "qa-sess", "engine": "native", "mode": "execution", "role": "qa"},
        )
        session_id = create_resp.json()["id"]
        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["role"] == "qa"


# ---------------------------------------------------------------------------
# Integration: Pipeline transition with role enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPipelineTransitionRoleEnforcement:
    async def _create_session(self, client: AsyncClient, project: Project, role: str | None) -> str:
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": f"s-{role or 'none'}",
                "engine": "native",
                "mode": "execution",
                "role": role,
            },
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def _create_task(self, client: AsyncClient, session_id: str) -> str:
        resp = await client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "pipeline task"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_pm_valid_transition_200(self, client: AsyncClient, project: Project):
        pm_id = await self._create_session(client, project, "pm")
        task_id = await self._create_task(client, pm_id)
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming", "actor_session_id": pm_id},
        )
        assert resp.status_code == 200
        assert resp.json()["pipeline_status"] == "grooming"

    async def test_swe_invalid_transition_403(self, client: AsyncClient, project: Project):
        swe_id = await self._create_session(client, project, "swe")
        task_id = await self._create_task(client, swe_id)
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming", "actor_session_id": swe_id},
        )
        assert resp.status_code == 403
        assert "swe" in resp.json()["detail"]
        assert "not allowed" in resp.json()["detail"]

    async def test_legacy_no_actor_session_200(self, client: AsyncClient, project: Project):
        pm_id = await self._create_session(client, project, "pm")
        task_id = await self._create_task(client, pm_id)
        # No actor_session_id -- legacy behavior
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Integration: Roles API (list, get, patch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRolesAPIEndpoints:
    async def test_list_roles_includes_pipeline_roles(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        # Seed roles first
        await seed_builtin_roles(db_session)
        resp = await client.get("/api/roles")
        assert resp.status_code == 200
        data = resp.json()
        names = [r["name"] for r in data]
        assert "pm" in names
        assert "swe" in names
        assert "qa" in names
        assert "oncall" in names

    async def test_get_pipeline_role(self, client: AsyncClient, db_session: AsyncSession):
        await seed_builtin_roles(db_session)
        resp = await client.get("/api/roles/pm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "pm"
        assert data["display_name"] == "Product Manager"
        assert data["color"] == "blue"
        assert data["is_builtin"] is True
        assert "allowed_transitions" in data

    async def test_get_nonexistent_role_404(self, client: AsyncClient):
        resp = await client.get("/api/roles/nonexistent")
        assert resp.status_code == 404

    async def test_patch_pipeline_role(self, client: AsyncClient, db_session: AsyncSession):
        await seed_builtin_roles(db_session)
        resp = await client.patch(
            "/api/roles/pm",
            json={"system_prompt": "You are an updated PM agent.", "color": "purple"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_prompt"] == "You are an updated PM agent."
        assert data["color"] == "purple"
        # display_name unchanged
        assert data["display_name"] == "Product Manager"

    async def test_patch_nonexistent_role_404(self, client: AsyncClient):
        resp = await client.patch(
            "/api/roles/nonexistent",
            json={"system_prompt": "New prompt"},
        )
        assert resp.status_code == 404
