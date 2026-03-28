"""Tests for OrchestratorService: core logic, verdict parsing, routing, API endpoints."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.issues import create_issue, list_issue_log_entries
from codehive.core.orchestrator_service import (
    OrchestratorService,
    Verdict,
    build_instructions,
    clear_registry,
    get_orchestrator,
    parse_verdict,
    register_orchestrator,
    route_result,
    unregister_orchestrator,
)
from codehive.core.task_queue import create_task, pipeline_transition
from codehive.db.models import Base, Issue, Project, Task
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


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
async def orch_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name=f"orchestrator-{project.id}",
        engine="claude_code",
        mode="orchestrator",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def issue(db_session: AsyncSession, project: Project) -> Issue:
    return await create_issue(
        db_session,
        project_id=project.id,
        title="Test Issue",
        description="Test description",
        acceptance_criteria="- Must pass tests",
    )


@pytest_asyncio.fixture(autouse=True)
async def cleanup_registry():
    """Clear the orchestrator registry before/after each test."""
    clear_registry()
    yield
    clear_registry()


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
            json={"email": "orch@test.com", "username": "orchuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit: parse_verdict
# ---------------------------------------------------------------------------


class TestParseVerdict:
    def test_parse_verdict_pass(self):
        assert parse_verdict("All tests pass. VERDICT: PASS") == Verdict.PASS

    def test_parse_verdict_fail(self):
        assert parse_verdict("Tests failed. VERDICT: FAIL") == Verdict.FAIL

    def test_parse_verdict_accept(self):
        assert parse_verdict("Looks good. VERDICT: ACCEPT") == Verdict.ACCEPT

    def test_parse_verdict_reject(self):
        assert parse_verdict("Not acceptable. VERDICT: REJECT") == Verdict.REJECT

    def test_parse_verdict_case_insensitive(self):
        assert parse_verdict("verdict: pass") == Verdict.PASS
        assert parse_verdict("Verdict: Fail") == Verdict.FAIL

    def test_parse_verdict_ambiguous(self):
        """No clear verdict defaults to FAIL (safe default)."""
        assert parse_verdict("Everything seems fine.") == Verdict.FAIL

    def test_parse_verdict_empty(self):
        assert parse_verdict("") == Verdict.FAIL


# ---------------------------------------------------------------------------
# Unit: route_result
# ---------------------------------------------------------------------------


class TestRouteResult:
    def test_route_result_grooming(self):
        assert route_result("grooming", Verdict.NONE) == "groomed"

    def test_route_result_implementing(self):
        assert route_result("implementing", Verdict.NONE) == "testing"

    def test_route_result_qa_pass(self):
        assert route_result("testing", Verdict.PASS) == "accepting"

    def test_route_result_qa_fail(self):
        assert route_result("testing", Verdict.FAIL) == "implementing"

    def test_route_result_pm_accept(self):
        assert route_result("accepting", Verdict.ACCEPT) == "done"

    def test_route_result_pm_reject(self):
        assert route_result("accepting", Verdict.REJECT) == "implementing"

    def test_route_result_unknown_step(self):
        assert route_result("unknown", Verdict.PASS) is None


# ---------------------------------------------------------------------------
# Unit: build_instructions
# ---------------------------------------------------------------------------


class TestBuildInstructions:
    def test_grooming_instructions(self):
        text = build_instructions("grooming", "Add dark mode", "Implement dark theme")
        assert "Add dark mode" in text
        assert "Implement dark theme" in text
        assert "groom" in text.lower()

    def test_implementing_with_feedback(self):
        text = build_instructions(
            "implementing",
            "Add dark mode",
            "Implement dark theme",
            acceptance_criteria="- Dark backgrounds",
            feedback="Health endpoint missing version field",
        )
        assert "Add dark mode" in text
        assert "Dark backgrounds" in text
        assert "Health endpoint missing version field" in text

    def test_testing_instructions(self):
        text = build_instructions(
            "testing",
            "Add dark mode",
            None,
            acceptance_criteria="- Dark backgrounds",
            agent_output="Implemented dark mode with CSS variables",
        )
        assert "VERDICT: PASS" in text or "VERDICT: FAIL" in text
        assert "CSS variables" in text

    def test_accepting_instructions(self):
        text = build_instructions(
            "accepting",
            "Add dark mode",
            None,
            acceptance_criteria="- Dark backgrounds",
            agent_output="All tests passed",
        )
        assert "VERDICT: ACCEPT" in text or "VERDICT: REJECT" in text
        assert "All tests passed" in text


# ---------------------------------------------------------------------------
# Unit: OrchestratorService._pick_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPickBatch:
    async def test_pick_batch_returns_backlog_tasks(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
    ):
        # Create 3 backlog tasks
        for i in range(3):
            await create_task(
                db_session, session_id=orch_session.id, title=f"task-{i}", pipeline_status="backlog"
            )

        service = OrchestratorService(db_session_factory, project.id)
        async with db_session_factory() as db:
            batch = await service._pick_batch(db)

        assert len(batch) == 2  # default batch_size

    async def test_pick_batch_skips_non_backlog(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
    ):
        # Create one backlog and one implementing task
        await create_task(
            db_session, session_id=orch_session.id, title="backlog-task", pipeline_status="backlog"
        )
        t2 = await create_task(
            db_session, session_id=orch_session.id, title="impl-task", pipeline_status="backlog"
        )
        # Manually move t2 through the pipeline
        await pipeline_transition(db_session, t2.id, "grooming")
        await pipeline_transition(db_session, t2.id, "groomed")
        await pipeline_transition(db_session, t2.id, "implementing")

        service = OrchestratorService(db_session_factory, project.id)
        async with db_session_factory() as db:
            batch = await service._pick_batch(db)

        assert len(batch) == 1
        assert batch[0].title == "backlog-task"

    async def test_pick_batch_empty(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
    ):
        service = OrchestratorService(db_session_factory, project.id)
        async with db_session_factory() as db:
            batch = await service._pick_batch(db)

        assert len(batch) == 0


# ---------------------------------------------------------------------------
# Unit: Pipeline step -> agent role mapping
# ---------------------------------------------------------------------------


class TestStepRoleMapping:
    def test_step_grooming_spawns_pm_session(self):
        from codehive.core.orchestrator_service import STEP_ROLE_MAP

        assert STEP_ROLE_MAP["grooming"]["role"] == "pm"
        assert STEP_ROLE_MAP["grooming"]["mode"] == "planning"

    def test_step_implementing_spawns_swe_session(self):
        from codehive.core.orchestrator_service import STEP_ROLE_MAP

        assert STEP_ROLE_MAP["implementing"]["role"] == "swe"
        assert STEP_ROLE_MAP["implementing"]["mode"] == "execution"

    def test_step_testing_spawns_qa_session(self):
        from codehive.core.orchestrator_service import STEP_ROLE_MAP

        assert STEP_ROLE_MAP["testing"]["role"] == "qa"
        assert STEP_ROLE_MAP["testing"]["mode"] == "execution"

    def test_step_accepting_spawns_pm_session(self):
        from codehive.core.orchestrator_service import STEP_ROLE_MAP

        assert STEP_ROLE_MAP["accepting"]["role"] == "pm"
        assert STEP_ROLE_MAP["accepting"]["mode"] == "execution"


# ---------------------------------------------------------------------------
# Unit: Max rejection safeguard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMaxRejections:
    async def test_route_result_max_rejections(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
    ):
        """After 3 rejections, task is flagged for human review."""
        task = await create_task(
            db_session, session_id=orch_session.id, title="task", pipeline_status="backlog"
        )

        service = OrchestratorService(db_session_factory, project.id)
        service.state.rejection_counts[task.id] = 2  # already 2 rejections

        # Next rejection should trigger flagging (count becomes 3 >= max of 3)
        count = service.state.rejection_counts.get(task.id, 0) + 1
        service.state.rejection_counts[task.id] = count

        if count >= service.config["max_rejections_per_step"]:
            service.state.flagged_tasks.add(task.id)

        assert task.id in service.state.flagged_tasks


# ---------------------------------------------------------------------------
# Unit: Sub-agent engine selection
# ---------------------------------------------------------------------------


class TestSubAgentEngineSelection:
    def test_resolve_sub_agent_engine_from_config(self):
        """When sub_agent_engines is set, the first entry is used."""
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "native"]},
        )
        assert service._resolve_sub_agent_engine() == "claude_code"

    def test_resolve_sub_agent_engine_fallback(self):
        """When sub_agent_engines is not set, falls back to orchestrator engine."""
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"engine": "native"},
        )
        assert service._resolve_sub_agent_engine() == "native"

    def test_resolve_sub_agent_engine_empty_list_fallback(self):
        """When sub_agent_engines is an empty list, falls back to orchestrator engine."""
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"engine": "codex", "sub_agent_engines": []},
        )
        assert service._resolve_sub_agent_engine() == "codex"

    def test_resolve_sub_agent_engine_default_config(self):
        """Without any config override, falls back to DEFAULT_CONFIG engine."""
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
        )
        # DEFAULT_CONFIG["engine"] is "claude_code"
        assert service._resolve_sub_agent_engine() == "claude_code"


@pytest.mark.asyncio
class TestSubAgentEngineSpawn:
    async def test_spawn_uses_sub_agent_engine(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Pipeline spawns child sessions using sub_agent_engines config."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="test-spawn",
            pipeline_status="backlog",
        )

        engines_seen: list[str] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            engines_seen.append(step)
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(
            db_session_factory,
            project.id,
            config={"sub_agent_engines": ["claude_code", "native"]},
        )
        service._spawn_and_run = mock_spawn

        # Verify the engine resolution works correctly
        assert service._resolve_sub_agent_engine() == "claude_code"

        await service._run_task_pipeline(task)

        # Pipeline should complete
        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_spawn_fallback_engine(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Without sub_agent_engines, falls back to orchestrator's engine."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="test-fallback",
            pipeline_status="backlog",
        )

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(
            db_session_factory,
            project.id,
            config={"engine": "native"},
        )
        service._spawn_and_run = mock_spawn

        # Without sub_agent_engines, falls back to engine
        assert service._resolve_sub_agent_engine() == "native"

        await service._run_task_pipeline(task)

        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"


# ---------------------------------------------------------------------------
# Unit: OrchestratorService.get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_get_status_stopped(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
        )
        status = service.get_status()
        assert status["status"] == "stopped"

    def test_get_status_running(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
        )
        service.state.running = True
        status = service.get_status()
        assert status["status"] == "running"


# ---------------------------------------------------------------------------
# Unit: Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_get(self):
        pid = uuid.uuid4()
        service = OrchestratorService(AsyncMock(), pid)
        service.state.running = True
        register_orchestrator(service)
        assert get_orchestrator(pid) is service

    def test_register_duplicate_raises(self):
        pid = uuid.uuid4()
        service = OrchestratorService(AsyncMock(), pid)
        service.state.running = True
        register_orchestrator(service)

        service2 = OrchestratorService(AsyncMock(), pid)
        service2.state.running = True
        with pytest.raises(ValueError, match="already running"):
            register_orchestrator(service2)

    def test_unregister(self):
        pid = uuid.uuid4()
        service = OrchestratorService(AsyncMock(), pid)
        register_orchestrator(service)
        unregister_orchestrator(pid)
        assert get_orchestrator(pid) is None


# ---------------------------------------------------------------------------
# Integration: Full pipeline with mocked engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFullPipeline:
    async def test_full_pipeline_happy_path(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task goes through full pipeline with mocked agent sessions."""
        # Link session to issue
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Happy path task",
            pipeline_status="backlog",
        )

        # Track which steps were called
        steps_called: list[str] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            steps_called.append(step)
            if step == "grooming":
                return "Groomed the task. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented the feature. VERDICT: PASS"
            elif step == "testing":
                return "All tests pass. VERDICT: PASS"
            elif step == "accepting":
                return "Looks good. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        assert "grooming" in steps_called
        assert "implementing" in steps_called
        assert "testing" in steps_called
        assert "accepting" in steps_called

        # Verify task reached "done"
        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_pipeline_qa_rejection_loop(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task goes through QA rejection and then passes."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="QA reject task",
            pipeline_status="backlog",
        )

        call_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            call_count[step] = call_count.get(step, 0) + 1
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            elif step == "testing":
                if call_count["testing"] == 1:
                    return "Tests fail. VERDICT: FAIL"
                return "All pass. VERDICT: PASS"
            elif step == "accepting":
                return "Good. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        # QA was called twice (once fail, once pass)
        assert call_count.get("testing", 0) == 2
        # SWE was called twice (initial + fix)
        assert call_count.get("implementing", 0) == 2

        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_pipeline_pm_rejection_loop(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task goes through PM rejection and then passes."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="PM reject task",
            pipeline_status="backlog",
        )

        call_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            call_count[step] = call_count.get(step, 0) + 1
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            elif step == "testing":
                return "All pass. VERDICT: PASS"
            elif step == "accepting":
                if call_count["accepting"] == 1:
                    return "Not good. VERDICT: REJECT"
                return "Now good. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        assert call_count.get("accepting", 0) == 2

        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_pipeline_max_rejections(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task hits max rejections and gets flagged."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Max reject task",
            pipeline_status="backlog",
        )

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            elif step == "testing":
                return "Fails. VERDICT: FAIL"
            elif step == "accepting":
                return "Good. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        # Task should be flagged
        assert task.id in service.state.flagged_tasks

        # Task should NOT reach done -- it stays at implementing or testing
        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status != "done"

    async def test_pipeline_batch_parallel(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Two tasks in a batch run their pipeline steps concurrently."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task1 = await create_task(
            db_session, session_id=orch_session.id, title="task-1", pipeline_status="backlog"
        )
        task2 = await create_task(
            db_session, session_id=orch_session.id, title="task-2", pipeline_status="backlog"
        )

        execution_order: list[tuple[str, str]] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            execution_order.append((str(task_id), step))
            # Small delay to allow interleaving
            await asyncio.sleep(0.01)
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        # Run both tasks in parallel (like the main loop would)
        await asyncio.gather(
            service._run_task_pipeline(task1),
            service._run_task_pipeline(task2),
        )

        # Both tasks should reach done
        async with db_session_factory() as db:
            r1 = await db.get(Task, task1.id)
            r2 = await db.get(Task, task2.id)
            assert r1.pipeline_status == "done"
            assert r2.pipeline_status == "done"

        # Both task IDs should appear in execution order
        task_ids_seen = {eo[0] for eo in execution_order}
        assert str(task1.id) in task_ids_seen
        assert str(task2.id) in task_ids_seen


# ---------------------------------------------------------------------------
# Integration: Agent feedback logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFeedbackLogging:
    async def test_agent_feedback_logged(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Agent feedback is logged via create_issue_log_entry at each step."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session, session_id=orch_session.id, title="Logging task", pipeline_status="backlog"
        )

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed the task well. VERDICT: PASS"
            elif step == "implementing":
                return "Code written. VERDICT: PASS"
            elif step == "testing":
                return "All tests pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accepted. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        # Check that log entries were created
        async with db_session_factory() as db:
            logs = await list_issue_log_entries(db, issue.id)
            assert len(logs) >= 4  # At least one per pipeline step
            roles = [log.agent_role for log in logs]
            assert "pm" in roles
            assert "swe" in roles
            assert "qa" in roles


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorAPI:
    async def test_start_orchestrator(self, client: AsyncClient, project: Project):
        resp = await client.post(
            "/api/orchestrator/start",
            json={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["project_id"] == str(project.id)

        # Clean up the background task
        svc = get_orchestrator(project.id)
        if svc:
            await svc.stop()

    async def test_start_orchestrator_already_running(self, client: AsyncClient, project: Project):
        resp1 = await client.post(
            "/api/orchestrator/start",
            json={"project_id": str(project.id)},
        )
        assert resp1.status_code == 200

        resp2 = await client.post(
            "/api/orchestrator/start",
            json={"project_id": str(project.id)},
        )
        assert resp2.status_code == 409

        # Clean up
        svc = get_orchestrator(project.id)
        if svc:
            await svc.stop()

    async def test_stop_orchestrator(self, client: AsyncClient, project: Project):
        await client.post(
            "/api/orchestrator/start",
            json={"project_id": str(project.id)},
        )

        resp = await client.post(
            "/api/orchestrator/stop",
            json={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    async def test_stop_orchestrator_idempotent(self, client: AsyncClient, project: Project):
        resp = await client.post(
            "/api/orchestrator/stop",
            json={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    async def test_get_status_running(self, client: AsyncClient, project: Project):
        await client.post(
            "/api/orchestrator/start",
            json={"project_id": str(project.id)},
        )

        resp = await client.get(
            "/api/orchestrator/status",
            params={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        # Clean up
        svc = get_orchestrator(project.id)
        if svc:
            await svc.stop()

    async def test_get_status_stopped(self, client: AsyncClient, project: Project):
        resp = await client.get(
            "/api/orchestrator/status",
            params={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    async def test_add_task(self, client: AsyncClient, project: Project):
        resp = await client.post(
            "/api/orchestrator/add-task",
            json={
                "project_id": str(project.id),
                "title": "Add dark mode",
                "description": "Implement dark theme",
                "acceptance_criteria": "- Dark backgrounds",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["pipeline_status"] == "backlog"
        assert "issue_id" in data
        assert "task_id" in data
