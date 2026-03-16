"""Tests for permissions and authorization (issue #59b)."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, Table, UniqueConstraint, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.permissions import ROLE_HIERARCHY, check_project_access, check_workspace_access
from codehive.db.models import Base, Project, User, Workspace, WorkspaceMember

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


def _sqlite_compatible_metadata() -> MetaData:
    """Return a copy of Base.metadata with SQLite-compatible types and defaults."""
    metadata = MetaData()

    for table in Base.metadata.tables.values():
        columns = []
        for col in table.columns:
            col_copy = col._copy()

            if col_copy.type.__class__.__name__ == "JSONB":
                col_copy.type = JSON()

            if col_copy.server_default is not None:
                default_text = str(col_copy.server_default.arg)
                if "::jsonb" in default_text:
                    col_copy.server_default = text("'{}'")
                elif "now()" in default_text:
                    col_copy.server_default = text("(datetime('now'))")
                elif default_text == "true":
                    col_copy.server_default = text("1")
                elif default_text == "false":
                    col_copy.server_default = text("0")

            columns.append(col_copy)

        # Copy table-level constraints (e.g. UniqueConstraint)
        constraints = []
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint) and len(constraint.columns) > 1:
                col_names = [c.name for c in constraint.columns]
                constraints.append(UniqueConstraint(*col_names))

        Table(table.name, metadata, *columns, *constraints)

    return metadata


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sqlite_metadata = _sqlite_compatible_metadata()

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_user(
    client: AsyncClient,
    email: str = "test@example.com",
    username: str = "testuser",
    password: str = "secret123",
) -> dict:
    """Register a user, return {access_token, user_id, ...}."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201
    data = resp.json()
    # Get the user id from the me endpoint
    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    me_data = me_resp.json()
    data["user_id"] = me_data["id"]
    return data


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_workspace(client: AsyncClient, token: str, name: str) -> dict:
    """Create a workspace and return its data."""
    resp = await client.post(
        "/api/workspaces",
        json={"name": name, "root_path": f"/tmp/{name}"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def _add_member(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    user_id: str,
    role: str,
) -> dict:
    """Add a member to a workspace."""
    resp = await client.post(
        f"/api/workspaces/{workspace_id}/members",
        json={"user_id": user_id, "role": role},
        headers=_auth_headers(token),
    )
    return (
        resp.json() if resp.status_code == 201 else {"status_code": resp.status_code, **resp.json()}
    )


async def _setup_db_fixtures(db: AsyncSession):
    """Create users, workspace, membership rows directly in the DB for unit tests."""
    from codehive.core.auth import hash_password

    user_owner = User(
        id=uuid.uuid4(),
        email="owner@test.com",
        username="owner",
        password_hash=hash_password("pass"),
        created_at=datetime.now(timezone.utc),
    )
    user_admin = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        username="admin",
        password_hash=hash_password("pass"),
        created_at=datetime.now(timezone.utc),
    )
    user_member = User(
        id=uuid.uuid4(),
        email="member@test.com",
        username="member_user",
        password_hash=hash_password("pass"),
        created_at=datetime.now(timezone.utc),
    )
    user_viewer = User(
        id=uuid.uuid4(),
        email="viewer@test.com",
        username="viewer",
        password_hash=hash_password("pass"),
        created_at=datetime.now(timezone.utc),
    )
    user_outsider = User(
        id=uuid.uuid4(),
        email="outsider@test.com",
        username="outsider",
        password_hash=hash_password("pass"),
        created_at=datetime.now(timezone.utc),
    )

    ws = Workspace(
        id=uuid.uuid4(),
        name="test-ws",
        root_path="/tmp/test",
        settings={},
        created_at=datetime.now(timezone.utc),
    )

    db.add_all([user_owner, user_admin, user_member, user_viewer, user_outsider, ws])
    await db.commit()

    for user, role in [
        (user_owner, "owner"),
        (user_admin, "admin"),
        (user_member, "member"),
        (user_viewer, "viewer"),
    ]:
        m = WorkspaceMember(
            workspace_id=ws.id,
            user_id=user.id,
            role=role,
            created_at=datetime.now(timezone.utc),
        )
        db.add(m)
    await db.commit()

    project = Project(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.commit()

    return {
        "owner": user_owner,
        "admin": user_admin,
        "member": user_member,
        "viewer": user_viewer,
        "outsider": user_outsider,
        "workspace": ws,
        "project": project,
    }


# ---------------------------------------------------------------------------
# Unit: Role hierarchy
# ---------------------------------------------------------------------------


class TestRoleHierarchy:
    def test_hierarchy_values(self):
        assert ROLE_HIERARCHY["owner"] > ROLE_HIERARCHY["admin"]
        assert ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["member"]
        assert ROLE_HIERARCHY["member"] > ROLE_HIERARCHY["viewer"]


# ---------------------------------------------------------------------------
# Unit: check_workspace_access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckWorkspaceAccess:
    async def test_viewer_access_for_all_roles(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        for role_name in ["owner", "admin", "member", "viewer"]:
            user = fixtures[role_name]
            result = await check_workspace_access(db_session, user.id, ws_id, "viewer")
            assert result is not None

    async def test_member_access_fails_for_viewer(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await check_workspace_access(db_session, fixtures["viewer"].id, ws_id, "member")
        assert exc_info.value.status_code == 403

    async def test_member_access_succeeds_for_member_and_above(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        for role_name in ["owner", "admin", "member"]:
            result = await check_workspace_access(
                db_session, fixtures[role_name].id, ws_id, "member"
            )
            assert result is not None

    async def test_admin_access_fails_for_member_and_viewer(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        from fastapi import HTTPException

        for role_name in ["member", "viewer"]:
            with pytest.raises(HTTPException) as exc_info:
                await check_workspace_access(db_session, fixtures[role_name].id, ws_id, "admin")
            assert exc_info.value.status_code == 403

    async def test_admin_access_succeeds_for_owner_and_admin(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        for role_name in ["owner", "admin"]:
            result = await check_workspace_access(
                db_session, fixtures[role_name].id, ws_id, "admin"
            )
            assert result is not None

    async def test_owner_access_only_for_owner(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        result = await check_workspace_access(db_session, fixtures["owner"].id, ws_id, "owner")
        assert result is not None

        from fastapi import HTTPException

        for role_name in ["admin", "member", "viewer"]:
            with pytest.raises(HTTPException) as exc_info:
                await check_workspace_access(db_session, fixtures[role_name].id, ws_id, "owner")
            assert exc_info.value.status_code == 403

    async def test_non_member_raises_403(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        ws_id = fixtures["workspace"].id

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await check_workspace_access(db_session, fixtures["outsider"].id, ws_id, "viewer")
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Unit: check_project_access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckProjectAccess:
    async def test_project_access_via_workspace_membership(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        project_id = fixtures["project"].id

        result = await check_project_access(db_session, fixtures["member"].id, project_id, "viewer")
        assert result is not None

    async def test_project_access_denied_for_non_member(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)
        project_id = fixtures["project"].id

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await check_project_access(db_session, fixtures["outsider"].id, project_id, "viewer")
        assert exc_info.value.status_code == 403

    async def test_project_not_found(self, db_session: AsyncSession):
        fixtures = await _setup_db_fixtures(db_session)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await check_project_access(db_session, fixtures["owner"].id, uuid.uuid4(), "viewer")
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Integration: Workspace route protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWorkspaceRouteProtection:
    async def test_unauthenticated_get_workspaces_401(self, client: AsyncClient):
        resp = await client.get("/api/workspaces")
        assert resp.status_code == 401

    async def test_create_workspace_auto_owner(self, client: AsyncClient):
        user = await _register_user(client, email="ws-owner@test.com", username="ws_owner")
        token = user["access_token"]

        ws = await _create_workspace(client, token, "auto-own-ws")
        ws_id = ws["id"]

        # Check membership
        resp = await client.get(
            f"/api/workspaces/{ws_id}/members",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 1
        assert members[0]["role"] == "owner"
        assert members[0]["user_id"] == user["user_id"]

    async def test_non_member_cannot_get_workspace(self, client: AsyncClient):
        user_a = await _register_user(client, email="a@test.com", username="user_a")
        user_b = await _register_user(client, email="b@test.com", username="user_b")

        ws = await _create_workspace(client, user_a["access_token"], "private-ws")

        resp = await client.get(
            f"/api/workspaces/{ws['id']}",
            headers=_auth_headers(user_b["access_token"]),
        )
        assert resp.status_code == 403

    async def test_owner_can_delete_workspace(self, client: AsyncClient):
        user = await _register_user(client, email="del-owner@test.com", username="del_owner")
        ws = await _create_workspace(client, user["access_token"], "del-ws")

        resp = await client.delete(
            f"/api/workspaces/{ws['id']}",
            headers=_auth_headers(user["access_token"]),
        )
        assert resp.status_code == 204

    async def test_admin_cannot_delete_workspace(self, client: AsyncClient):
        owner = await _register_user(client, email="own2@test.com", username="own2")
        admin = await _register_user(client, email="adm2@test.com", username="adm2")

        ws = await _create_workspace(client, owner["access_token"], "admin-del-ws")
        await _add_member(client, owner["access_token"], ws["id"], admin["user_id"], "admin")

        resp = await client.delete(
            f"/api/workspaces/{ws['id']}",
            headers=_auth_headers(admin["access_token"]),
        )
        assert resp.status_code == 403

    async def test_list_workspaces_filters_by_membership(self, client: AsyncClient):
        user_a = await _register_user(client, email="filt_a@test.com", username="filt_a")
        user_b = await _register_user(client, email="filt_b@test.com", username="filt_b")

        await _create_workspace(client, user_a["access_token"], "ws-for-a")
        await _create_workspace(client, user_b["access_token"], "ws-for-b")

        resp_a = await client.get(
            "/api/workspaces",
            headers=_auth_headers(user_a["access_token"]),
        )
        assert resp_a.status_code == 200
        names_a = [w["name"] for w in resp_a.json()]
        assert "ws-for-a" in names_a
        assert "ws-for-b" not in names_a


# ---------------------------------------------------------------------------
# Integration: Project route protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProjectRouteProtection:
    async def test_member_can_create_project(self, client: AsyncClient):
        owner = await _register_user(client, email="pown@test.com", username="pown")
        member = await _register_user(client, email="pmem@test.com", username="pmem")

        ws = await _create_workspace(client, owner["access_token"], "proj-ws")
        await _add_member(client, owner["access_token"], ws["id"], member["user_id"], "member")

        resp = await client.post(
            "/api/projects",
            json={"workspace_id": ws["id"], "name": "my-proj"},
            headers=_auth_headers(member["access_token"]),
        )
        assert resp.status_code == 201

    async def test_viewer_cannot_create_project(self, client: AsyncClient):
        owner = await _register_user(client, email="vpown@test.com", username="vpown")
        viewer = await _register_user(client, email="vview@test.com", username="vview")

        ws = await _create_workspace(client, owner["access_token"], "vproj-ws")
        await _add_member(client, owner["access_token"], ws["id"], viewer["user_id"], "viewer")

        resp = await client.post(
            "/api/projects",
            json={"workspace_id": ws["id"], "name": "view-proj"},
            headers=_auth_headers(viewer["access_token"]),
        )
        assert resp.status_code == 403

    async def test_viewer_can_get_project(self, client: AsyncClient):
        owner = await _register_user(client, email="vgown@test.com", username="vgown")
        viewer = await _register_user(client, email="vgview@test.com", username="vgview")

        ws = await _create_workspace(client, owner["access_token"], "vget-ws")
        await _add_member(client, owner["access_token"], ws["id"], viewer["user_id"], "viewer")

        proj_resp = await client.post(
            "/api/projects",
            json={"workspace_id": ws["id"], "name": "viewable-proj"},
            headers=_auth_headers(owner["access_token"]),
        )
        proj_id = proj_resp.json()["id"]

        resp = await client.get(
            f"/api/projects/{proj_id}",
            headers=_auth_headers(viewer["access_token"]),
        )
        assert resp.status_code == 200

    async def test_non_member_cannot_get_project(self, client: AsyncClient):
        owner = await _register_user(client, email="nmown@test.com", username="nmown")
        outsider = await _register_user(client, email="nmout@test.com", username="nmout")

        ws = await _create_workspace(client, owner["access_token"], "nmproj-ws")
        proj_resp = await client.post(
            "/api/projects",
            json={"workspace_id": ws["id"], "name": "secret-proj"},
            headers=_auth_headers(owner["access_token"]),
        )
        proj_id = proj_resp.json()["id"]

        resp = await client.get(
            f"/api/projects/{proj_id}",
            headers=_auth_headers(outsider["access_token"]),
        )
        assert resp.status_code == 403

    async def test_list_projects_filters_by_membership(self, client: AsyncClient):
        user_a = await _register_user(client, email="lpfa@test.com", username="lpfa")
        user_b = await _register_user(client, email="lpfb@test.com", username="lpfb")

        ws_a = await _create_workspace(client, user_a["access_token"], "lpf-ws-a")
        ws_b = await _create_workspace(client, user_b["access_token"], "lpf-ws-b")

        await client.post(
            "/api/projects",
            json={"workspace_id": ws_a["id"], "name": "proj-a"},
            headers=_auth_headers(user_a["access_token"]),
        )
        await client.post(
            "/api/projects",
            json={"workspace_id": ws_b["id"], "name": "proj-b"},
            headers=_auth_headers(user_b["access_token"]),
        )

        resp = await client.get(
            "/api/projects",
            headers=_auth_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "proj-a" in names
        assert "proj-b" not in names


# ---------------------------------------------------------------------------
# Integration: Session route protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSessionRouteProtection:
    async def _setup_project(self, client: AsyncClient):
        """Create owner, viewer, outsider, workspace, project for session tests."""
        owner = await _register_user(client, email="sown@test.com", username="sown")
        viewer = await _register_user(client, email="sview@test.com", username="sview")
        outsider = await _register_user(client, email="sout@test.com", username="sout")

        ws = await _create_workspace(client, owner["access_token"], "sess-ws")
        await _add_member(client, owner["access_token"], ws["id"], viewer["user_id"], "viewer")

        proj_resp = await client.post(
            "/api/projects",
            json={"workspace_id": ws["id"], "name": "sess-proj"},
            headers=_auth_headers(owner["access_token"]),
        )
        proj = proj_resp.json()

        return {"owner": owner, "viewer": viewer, "outsider": outsider, "project": proj}

    async def test_member_can_create_session(self, client: AsyncClient):
        setup = await self._setup_project(client)
        resp = await client.post(
            f"/api/projects/{setup['project']['id']}/sessions",
            json={"name": "s1", "engine": "native", "mode": "execution"},
            headers=_auth_headers(setup["owner"]["access_token"]),
        )
        assert resp.status_code == 201

    async def test_viewer_cannot_create_session(self, client: AsyncClient):
        setup = await self._setup_project(client)
        resp = await client.post(
            f"/api/projects/{setup['project']['id']}/sessions",
            json={"name": "s2", "engine": "native", "mode": "execution"},
            headers=_auth_headers(setup["viewer"]["access_token"]),
        )
        assert resp.status_code == 403

    async def test_viewer_can_read_session(self, client: AsyncClient):
        setup = await self._setup_project(client)

        # Create session as owner
        create_resp = await client.post(
            f"/api/projects/{setup['project']['id']}/sessions",
            json={"name": "readable", "engine": "native", "mode": "execution"},
            headers=_auth_headers(setup["owner"]["access_token"]),
        )
        session_id = create_resp.json()["id"]

        # Viewer reads
        resp = await client.get(
            f"/api/sessions/{session_id}",
            headers=_auth_headers(setup["viewer"]["access_token"]),
        )
        assert resp.status_code == 200

    async def test_non_member_cannot_read_session(self, client: AsyncClient):
        setup = await self._setup_project(client)

        create_resp = await client.post(
            f"/api/projects/{setup['project']['id']}/sessions",
            json={"name": "secret-sess", "engine": "native", "mode": "execution"},
            headers=_auth_headers(setup["owner"]["access_token"]),
        )
        session_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/sessions/{session_id}",
            headers=_auth_headers(setup["outsider"]["access_token"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Integration: Membership management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMembershipManagement:
    async def test_owner_adds_member(self, client: AsyncClient):
        owner = await _register_user(client, email="mown@test.com", username="mown")
        new_user = await _register_user(client, email="mnew@test.com", username="mnew")

        ws = await _create_workspace(client, owner["access_token"], "mem-ws")

        resp = await client.post(
            f"/api/workspaces/{ws['id']}/members",
            json={"user_id": new_user["user_id"], "role": "member"},
            headers=_auth_headers(owner["access_token"]),
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "member"

    async def test_member_cannot_add_member(self, client: AsyncClient):
        owner = await _register_user(client, email="mmown@test.com", username="mmown")
        mem = await _register_user(client, email="mmmem@test.com", username="mmmem")
        new_user = await _register_user(client, email="mmnew@test.com", username="mmnew")

        ws = await _create_workspace(client, owner["access_token"], "mem-restrict-ws")
        await _add_member(client, owner["access_token"], ws["id"], mem["user_id"], "member")

        resp = await client.post(
            f"/api/workspaces/{ws['id']}/members",
            json={"user_id": new_user["user_id"], "role": "member"},
            headers=_auth_headers(mem["access_token"]),
        )
        assert resp.status_code == 403

    async def test_admin_changes_role(self, client: AsyncClient):
        owner = await _register_user(client, email="rcown@test.com", username="rcown")
        admin = await _register_user(client, email="rcadm@test.com", username="rcadm")
        mem = await _register_user(client, email="rcmem@test.com", username="rcmem")

        ws = await _create_workspace(client, owner["access_token"], "role-change-ws")
        await _add_member(client, owner["access_token"], ws["id"], admin["user_id"], "admin")
        await _add_member(client, owner["access_token"], ws["id"], mem["user_id"], "member")

        resp = await client.patch(
            f"/api/workspaces/{ws['id']}/members/{mem['user_id']}",
            json={"role": "admin"},
            headers=_auth_headers(admin["access_token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_cannot_change_owner_role(self, client: AsyncClient):
        owner = await _register_user(client, email="coown@test.com", username="coown")
        admin = await _register_user(client, email="coadm@test.com", username="coadm")

        ws = await _create_workspace(client, owner["access_token"], "no-change-owner-ws")
        await _add_member(client, owner["access_token"], ws["id"], admin["user_id"], "admin")

        resp = await client.patch(
            f"/api/workspaces/{ws['id']}/members/{owner['user_id']}",
            json={"role": "member"},
            headers=_auth_headers(admin["access_token"]),
        )
        assert resp.status_code == 403

    async def test_admin_removes_member(self, client: AsyncClient):
        owner = await _register_user(client, email="rmown@test.com", username="rmown")
        admin = await _register_user(client, email="rmadm@test.com", username="rmadm")
        mem = await _register_user(client, email="rmmem@test.com", username="rmmem")

        ws = await _create_workspace(client, owner["access_token"], "remove-ws")
        await _add_member(client, owner["access_token"], ws["id"], admin["user_id"], "admin")
        await _add_member(client, owner["access_token"], ws["id"], mem["user_id"], "member")

        resp = await client.delete(
            f"/api/workspaces/{ws['id']}/members/{mem['user_id']}",
            headers=_auth_headers(admin["access_token"]),
        )
        assert resp.status_code == 204

    async def test_duplicate_member_409(self, client: AsyncClient):
        owner = await _register_user(client, email="dpown@test.com", username="dpown")
        mem = await _register_user(client, email="dpmem@test.com", username="dpmem")

        ws = await _create_workspace(client, owner["access_token"], "dup-mem-ws")
        await _add_member(client, owner["access_token"], ws["id"], mem["user_id"], "member")

        resp = await client.post(
            f"/api/workspaces/{ws['id']}/members",
            json={"user_id": mem["user_id"], "role": "viewer"},
            headers=_auth_headers(owner["access_token"]),
        )
        assert resp.status_code == 409

    async def test_list_members(self, client: AsyncClient):
        owner = await _register_user(client, email="lmown@test.com", username="lmown")
        mem = await _register_user(client, email="lmmem@test.com", username="lmmem")

        ws = await _create_workspace(client, owner["access_token"], "list-mem-ws")
        await _add_member(client, owner["access_token"], ws["id"], mem["user_id"], "viewer")

        resp = await client.get(
            f"/api/workspaces/{ws['id']}/members",
            headers=_auth_headers(owner["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2  # owner + viewer
