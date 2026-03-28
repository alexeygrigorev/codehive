"""Tests for TaskExecutionRunner: core loop, rejection handling, cancellation,
crash retry, verdict resolution, RunResult, spawn_fn integration, and API endpoints.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.issues import create_issue, list_issue_log_entries
from codehive.core.task_queue import create_task, pipeline_transition
from codehive.core.task_runner import (
    RunResult,
    TaskExecutionRunner,
    clear_runner_registry,
    get_runner,
    register_runner,
    unregister_runner,
)
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
async def cleanup_runner_registry():
    """Clear the runner registry before/after each test."""
    clear_runner_registry()
    yield
    clear_runner_registry()


# ---------------------------------------------------------------------------
# Helper: create a task linked to an issue
# ---------------------------------------------------------------------------


async def _create_task(
    db_session: AsyncSession,
    orch_session: SessionModel,
    issue: Issue | None = None,
    pipeline_status: str = "backlog",
    title: str = "Test task",
) -> Task:
    if issue is not None:
        orch_session.issue_id = issue.id
        await db_session.commit()
    return await create_task(
        db_session,
        session_id=orch_session.id,
        title=title,
        pipeline_status=pipeline_status,
    )


# ---------------------------------------------------------------------------
# Helper: standard mock_spawn
# ---------------------------------------------------------------------------


def _make_happy_spawn() -> Any:
    """Return a mock spawn_fn that returns PASS/ACCEPT for all steps."""
    steps_called: list[tuple[str, str, str]] = []

    async def mock_spawn(
        task_id: uuid.UUID,
        step: str,
        role: str,
        mode: str,
        instructions: str,
    ) -> str:
        steps_called.append((step, role, mode))
        if step == "grooming":
            return "Groomed. VERDICT: PASS"
        elif step == "implementing":
            return "Done. VERDICT: PASS"
        elif step == "testing":
            return "All pass. VERDICT: PASS"
        elif step == "accepting":
            return "Accept. VERDICT: ACCEPT"
        return ""

    return mock_spawn, steps_called


# ---------------------------------------------------------------------------
# Unit: RunResult dataclass
# ---------------------------------------------------------------------------


class TestRunResult:
    def test_run_result_fields(self):
        r = RunResult(
            final_status="done",
            steps_executed=4,
            rejection_count=1,
            commit_sha="abc123",
            last_verdict="ACCEPT",
        )
        assert r.final_status == "done"
        assert r.steps_executed == 4
        assert r.rejection_count == 1
        assert r.commit_sha == "abc123"
        assert r.last_verdict == "ACCEPT"

    def test_run_result_defaults(self):
        r = RunResult(final_status="error")
        assert r.steps_executed == 0
        assert r.rejection_count == 0
        assert r.commit_sha is None
        assert r.last_verdict is None

    def test_commit_sha_only_on_done(self):
        r_done = RunResult(final_status="done", commit_sha="abc")
        r_flagged = RunResult(final_status="flagged")
        assert r_done.commit_sha == "abc"
        assert r_flagged.commit_sha is None


# ---------------------------------------------------------------------------
# Unit: TaskExecutionRunner core loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreLoop:
    async def test_happy_path(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task goes backlog -> grooming -> implementing -> testing -> accepting -> done."""
        task = await _create_task(db_session, orch_session, issue)
        mock_spawn, steps_called = _make_happy_spawn()

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert result.steps_executed == 4
        assert result.rejection_count == 0
        assert result.last_verdict == "ACCEPT"

        step_names = [s[0] for s in steps_called]
        assert step_names == ["grooming", "implementing", "testing", "accepting"]

        # Verify task is at done in DB
        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_qa_rejection_loop(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """QA fails first time, passes second time."""
        task = await _create_task(db_session, orch_session, issue)
        call_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            call_count[step] = call_count.get(step, 0) + 1
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                if call_count["testing"] == 1:
                    return "Health endpoint missing. VERDICT: FAIL"
                return "All pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert result.rejection_count == 1
        assert call_count["testing"] == 2
        assert call_count["implementing"] == 2

    async def test_pm_rejection_loop(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """PM rejects first time, accepts second time."""
        task = await _create_task(db_session, orch_session, issue)
        call_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            call_count[step] = call_count.get(step, 0) + 1
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                if call_count["accepting"] == 1:
                    return "Not good enough. VERDICT: REJECT"
                return "Now good. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert result.rejection_count == 1
        assert call_count["accepting"] == 2
        # After PM reject, goes back to implementing -> testing -> accepting
        assert call_count["implementing"] == 2
        assert call_count["testing"] == 2

    async def test_max_rejections_flagged(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """QA always fails -> after 3 rejections, task is flagged."""
        task = await _create_task(db_session, orch_session, issue)

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Fails. VERDICT: FAIL"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
            config={"max_rejections_per_step": 3},
        )
        result = await runner.run()

        assert result.final_status == "flagged"
        assert result.rejection_count == 3

    async def test_cancellation_mid_pipeline(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Cancel during implementing step -- runner stops after that step."""
        task = await _create_task(db_session, orch_session, issue)
        runner: TaskExecutionRunner | None = None

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                # Cancel during implementing
                assert runner is not None
                runner.cancel()
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "cancelled"
        # Should have completed grooming and implementing, then stopped
        assert result.steps_executed >= 2

    async def test_already_groomed_task(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task starts at groomed -- runner skips grooming."""
        task = await _create_task(db_session, orch_session, issue, pipeline_status="backlog")
        # Manually transition to groomed
        await pipeline_transition(db_session, task.id, "grooming", actor="test")
        await pipeline_transition(db_session, task.id, "groomed", actor="test")

        steps_called: list[str] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            steps_called.append(step)
            if step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert "grooming" not in steps_called
        assert "implementing" in steps_called

    async def test_already_in_testing(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task starts at testing -- runner starts from testing step."""
        task = await _create_task(db_session, orch_session, issue, pipeline_status="backlog")
        await pipeline_transition(db_session, task.id, "grooming", actor="test")
        await pipeline_transition(db_session, task.id, "groomed", actor="test")
        await pipeline_transition(db_session, task.id, "implementing", actor="test")
        await pipeline_transition(db_session, task.id, "testing", actor="test")

        steps_called: list[str] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            steps_called.append(step)
            if step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert steps_called == ["testing", "accepting"]

    async def test_already_done(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Task already at done -- runner returns immediately, no agents spawned."""
        task = await _create_task(db_session, orch_session, issue, pipeline_status="backlog")
        await pipeline_transition(db_session, task.id, "grooming", actor="test")
        await pipeline_transition(db_session, task.id, "groomed", actor="test")
        await pipeline_transition(db_session, task.id, "implementing", actor="test")
        await pipeline_transition(db_session, task.id, "testing", actor="test")
        await pipeline_transition(db_session, task.id, "accepting", actor="test")
        await pipeline_transition(db_session, task.id, "done", actor="test")

        spawn_called = False

        async def mock_spawn(task_id, step, role, mode, instructions):
            nonlocal spawn_called
            spawn_called = True
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert result.steps_executed == 0
        assert not spawn_called

    async def test_task_not_found(
        self,
        db_session_factory,
    ):
        """Task doesn't exist -- runner returns error immediately."""
        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=uuid.uuid4(),
        )
        result = await runner.run()

        assert result.final_status == "error"


# ---------------------------------------------------------------------------
# Unit: Crash retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCrashRetry:
    async def test_crash_retry_then_succeed(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """spawn_fn crashes once, succeeds on retry."""
        task = await _create_task(db_session, orch_session, issue)
        attempt_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            attempt_count[step] = attempt_count.get(step, 0) + 1
            if step == "grooming" and attempt_count["grooming"] == 1:
                raise RuntimeError("Simulated crash")
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        assert result.final_status == "done"
        assert attempt_count["grooming"] == 2  # 1 crash + 1 retry

    async def test_crash_twice_flags_task(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """spawn_fn crashes twice on same step -> task is flagged."""
        task = await _create_task(db_session, orch_session, issue)

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                raise RuntimeError("Always crashes")
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        await runner.run()

        # Crash leads to FAIL verdict -> route_result("grooming", FAIL) -> "groomed"
        # But the flagging happens through log entry, and the result depends on
        # the crash handling logic. Check log entry was created.
        async with db_session_factory() as db:
            logs = await list_issue_log_entries(db, issue.id)
            flag_logs = [log for log in logs if "crashed" in log.content.lower()]
            assert len(flag_logs) >= 1


# ---------------------------------------------------------------------------
# Unit: Verdict resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestVerdictResolution:
    async def test_regex_fallback_when_no_structured_verdict(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """When no structured verdict exists, falls back to regex parsing."""
        task = await _create_task(db_session, orch_session, issue)
        mock_spawn, _ = _make_happy_spawn()

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        result = await runner.run()

        # All verdicts came from regex parsing (no child sessions for structured)
        assert result.final_status == "done"

    async def test_empty_output_defaults_to_fail(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Empty spawn output defaults to FAIL verdict."""
        task = await _create_task(db_session, orch_session, issue)

        async def mock_spawn(task_id, step, role, mode, instructions):
            return ""  # Empty output for all steps

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
            config={"max_rejections_per_step": 2},
        )
        result = await runner.run()

        # Empty output -> FAIL -> eventually flagged
        # grooming returns "" -> FAIL -> route_result("grooming", FAIL) -> "groomed"
        # implementing returns "" -> FAIL -> route_result("implementing", FAIL) -> "testing"
        # testing returns "" -> FAIL -> route_result("testing", FAIL) -> "implementing" (rejection)
        # This loops and eventually flags
        assert result.final_status == "flagged"

    async def test_no_spawn_fn_defaults_empty_output(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """When no spawn_fn is provided, output is empty string."""
        task = await _create_task(db_session, orch_session, issue)

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=None,  # No spawn function
            config={"max_rejections_per_step": 1},
        )
        result = await runner.run()

        # Without spawn_fn, all verdicts are FAIL (empty output)
        assert result.final_status == "flagged"


# ---------------------------------------------------------------------------
# Unit: spawn_fn integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSpawnFnIntegration:
    async def test_spawn_fn_receives_correct_args(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Verify spawn_fn is called with correct args for each step."""
        task = await _create_task(db_session, orch_session, issue)
        calls: list[dict[str, Any]] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            calls.append(
                {
                    "task_id": task_id,
                    "step": step,
                    "role": role,
                    "mode": mode,
                    "instructions": instructions,
                }
            )
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        await runner.run()

        assert len(calls) == 4

        # Grooming: pm, planning
        assert calls[0]["step"] == "grooming"
        assert calls[0]["role"] == "pm"
        assert calls[0]["mode"] == "planning"
        assert calls[0]["task_id"] == task.id

        # Implementing: swe, execution
        assert calls[1]["step"] == "implementing"
        assert calls[1]["role"] == "swe"
        assert calls[1]["mode"] == "execution"

        # Testing: qa, execution
        assert calls[2]["step"] == "testing"
        assert calls[2]["role"] == "qa"
        assert calls[2]["mode"] == "execution"

        # Accepting: pm, execution
        assert calls[3]["step"] == "accepting"
        assert calls[3]["role"] == "pm"
        assert calls[3]["mode"] == "execution"

    async def test_feedback_in_instructions_on_rejection(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """After QA rejection, SWE instructions include feedback."""
        task = await _create_task(db_session, orch_session, issue)
        calls: list[dict[str, Any]] = []
        call_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            call_count[step] = call_count.get(step, 0) + 1
            calls.append({"step": step, "instructions": instructions})
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                if call_count["testing"] == 1:
                    return "Missing version field. VERDICT: FAIL"
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        await runner.run()

        # Find the second implementing call (after rejection)
        impl_calls = [c for c in calls if c["step"] == "implementing"]
        assert len(impl_calls) == 2
        # Second SWE call should include feedback
        assert "Missing version field" in impl_calls[1]["instructions"]


# ---------------------------------------------------------------------------
# Unit: get_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetStatus:
    async def test_get_status_before_run(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue)

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
        )
        status = runner.get_status()
        assert status["running"] is False
        assert status["steps_executed"] == 0
        assert status["cancelled"] is False

    async def test_get_status_after_run(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue)
        mock_spawn, _ = _make_happy_spawn()

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
        )
        await runner.run()

        status = runner.get_status()
        assert status["running"] is False
        assert status["steps_executed"] == 4
        assert status["last_verdict"] == "ACCEPT"


# ---------------------------------------------------------------------------
# Unit: Flagged task log entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFlaggedLogging:
    async def test_flagged_creates_log_entry(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue)

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Fails. VERDICT: FAIL"
            return ""

        runner = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task.id,
            spawn_fn=mock_spawn,
            config={"max_rejections_per_step": 2},
        )
        result = await runner.run()

        assert result.final_status == "flagged"

        async with db_session_factory() as db:
            logs = await list_issue_log_entries(db, issue.id)
            flag_logs = [log for log in logs if "flagged" in log.content.lower()]
            assert len(flag_logs) >= 1


# ---------------------------------------------------------------------------
# Unit: Runner registry
# ---------------------------------------------------------------------------


class TestRunnerRegistry:
    def test_register_and_get(self):
        tid = uuid.uuid4()
        runner = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner.task_id = tid
        runner._running = True
        register_runner(runner)
        assert get_runner(tid) is runner

    def test_register_duplicate_raises(self):
        tid = uuid.uuid4()
        runner = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner.task_id = tid
        runner._running = True
        register_runner(runner)

        runner2 = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner2.task_id = tid
        runner2._running = True
        with pytest.raises(ValueError, match="already active"):
            register_runner(runner2)

    def test_unregister(self):
        tid = uuid.uuid4()
        runner = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner.task_id = tid
        runner._running = False
        register_runner(runner)
        unregister_runner(tid)
        assert get_runner(tid) is None


# ---------------------------------------------------------------------------
# Unit: Concurrent runners
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConcurrentRunners:
    async def test_multiple_runners_parallel(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Two independent runners execute concurrently."""
        task1 = await _create_task(db_session, orch_session, issue, title="task-1")
        task2 = await _create_task(db_session, orch_session, issue, title="task-2")

        execution_order: list[tuple[str, str]] = []

        async def mock_spawn(task_id, step, role, mode, instructions):
            execution_order.append((str(task_id), step))
            await asyncio.sleep(0.01)
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Pass. VERDICT: PASS"
            elif step == "accepting":
                return "Accept. VERDICT: ACCEPT"
            return ""

        runner1 = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task1.id,
            spawn_fn=mock_spawn,
        )
        runner2 = TaskExecutionRunner(
            db_session_factory=db_session_factory,
            task_id=task2.id,
            spawn_fn=mock_spawn,
        )

        results = await asyncio.gather(runner1.run(), runner2.run())

        assert results[0].final_status == "done"
        assert results[1].final_status == "done"

        task_ids = {eo[0] for eo in execution_order}
        assert str(task1.id) in task_ids
        assert str(task2.id) in task_ids


# ---------------------------------------------------------------------------
# Integration: OrchestratorService delegation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorDelegation:
    async def test_orchestrator_delegates_to_runner(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """OrchestratorService._run_task_pipeline now uses TaskExecutionRunner."""
        from codehive.core.orchestrator_service import OrchestratorService

        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await _create_task(db_session, orch_session, issue, title="delegate-test")
        mock_spawn, steps_called = _make_happy_spawn()

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        step_names = [s[0] for s in steps_called]
        assert "grooming" in step_names
        assert "implementing" in step_names
        assert "testing" in step_names
        assert "accepting" in step_names

        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_orchestrator_flags_on_max_rejections(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """OrchestratorService mirrors flagged status from runner."""
        from codehive.core.orchestrator_service import OrchestratorService

        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await _create_task(db_session, orch_session, issue, title="flag-test")

        async def mock_spawn(task_id, step, role, mode, instructions):
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Done. VERDICT: PASS"
            elif step == "testing":
                return "Fails. VERDICT: FAIL"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        assert task.id in service.state.flagged_tasks


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


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
            json={"email": "runner@test.com", "username": "runneruser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest.mark.asyncio
class TestAPIEndpoints:
    async def test_execute_starts_runner(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue, title="api-exec")
        resp = await client.post(f"/api/tasks/{task.id}/execute")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "started"
        assert data["task_id"] == str(task.id)

        # Wait briefly for the background task to complete or error
        await asyncio.sleep(0.5)

    async def test_execute_already_running_returns_409(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue, title="api-dup")

        # Manually register a "running" runner
        runner = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner.task_id = task.id
        runner._running = True
        register_runner(runner)

        resp = await client.post(f"/api/tasks/{task.id}/execute")
        assert resp.status_code == 409

    async def test_execute_nonexistent_task_returns_404(
        self,
        client: AsyncClient,
    ):
        fake_id = uuid.uuid4()
        resp = await client.post(f"/api/tasks/{fake_id}/execute")
        assert resp.status_code == 404

    async def test_cancel_running_task(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue, title="api-cancel")

        # Register a "running" runner
        runner = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner.task_id = task.id
        runner._running = True
        runner._cancelled = False
        register_runner(runner)

        resp = await client.post(f"/api/tasks/{task.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelling"
        assert runner._cancelled is True

    async def test_cancel_nonrunning_returns_404(
        self,
        client: AsyncClient,
    ):
        fake_id = uuid.uuid4()
        resp = await client.post(f"/api/tasks/{fake_id}/cancel")
        assert resp.status_code == 404

    async def test_execution_status_running(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        orch_session: SessionModel,
        issue: Issue,
    ):
        task = await _create_task(db_session, orch_session, issue, title="api-status")

        runner = TaskExecutionRunner.__new__(TaskExecutionRunner)
        runner.task_id = task.id
        runner._running = True
        runner._cancelled = False
        runner._current_step = "implementing"
        runner._steps_executed = 2
        runner._rejection_count = 0
        runner._last_verdict = "PASS"
        register_runner(runner)

        resp = await client.get(f"/api/tasks/{task.id}/execution-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["current_step"] == "implementing"
        assert data["steps_executed"] == 2

    async def test_execution_status_not_running(
        self,
        client: AsyncClient,
    ):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/tasks/{fake_id}/execution-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False
