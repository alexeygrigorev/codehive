"""Tests for structured verdict events: Pydantic models, submit, get, orchestrator fallback."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.core.orchestrator_service import (
    OrchestratorService,
    StepResult,
    Verdict,
    build_instructions,
)
from codehive.core.task_queue import create_task
from codehive.core.verdicts import (
    CriterionResult,
    EvidenceItem,
    VerdictPayload,
    VerdictValue,
    get_verdict,
    submit_verdict,
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

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # No explicit drop_all needed for in-memory SQLite; dispose closes the DB.
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
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="claude_code",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


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
    from codehive.core.issues import create_issue

    return await create_issue(
        db_session,
        project_id=project.id,
        title="Test Issue",
        description="Test description",
        acceptance_criteria="- Must pass tests",
    )


# ---------------------------------------------------------------------------
# Unit: Pydantic models
# ---------------------------------------------------------------------------


class TestVerdictPayload:
    def test_valid_pass(self):
        p = VerdictPayload(verdict="PASS", role="qa")
        assert p.verdict == VerdictValue.PASS

    def test_valid_fail(self):
        p = VerdictPayload(verdict="FAIL", role="qa")
        assert p.verdict == VerdictValue.FAIL

    def test_valid_accept(self):
        p = VerdictPayload(verdict="ACCEPT", role="pm")
        assert p.verdict == VerdictValue.ACCEPT

    def test_valid_reject(self):
        p = VerdictPayload(verdict="REJECT", role="pm")
        assert p.verdict == VerdictValue.REJECT

    def test_invalid_verdict_string(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VerdictPayload(verdict="MAYBE", role="qa")

    def test_full_payload(self):
        p = VerdictPayload(
            verdict="PASS",
            role="qa",
            task_id=str(uuid.uuid4()),
            evidence=[EvidenceItem(type="test_output", content="12 passed")],
            criteria_results=[CriterionResult(criterion="Health returns 200", result="PASS")],
            feedback="All good",
        )
        assert len(p.evidence) == 1
        assert len(p.criteria_results) == 1


class TestEvidenceItem:
    def test_with_content(self):
        e = EvidenceItem(type="test_output", content="12 passed, 0 failed")
        assert e.type == "test_output"
        assert e.content == "12 passed, 0 failed"

    def test_with_path(self):
        e = EvidenceItem(type="screenshot", path="/tmp/x.png")
        assert e.path == "/tmp/x.png"

    def test_empty_type_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceItem(type="  ", content="something")


class TestCriterionResult:
    def test_valid(self):
        c = CriterionResult(criterion="Health returns 200", result="PASS")
        assert c.criterion == "Health returns 200"
        assert c.result == "PASS"

    def test_with_detail(self):
        c = CriterionResult(criterion="Version field", result="FAIL", detail="missing")
        assert c.detail == "missing"

    def test_missing_criterion_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CriterionResult(criterion="  ", result="PASS")


# ---------------------------------------------------------------------------
# Unit: submit_verdict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubmitVerdict:
    async def test_submit_pass_verdict(self, db_session: AsyncSession, session: SessionModel):
        event = await submit_verdict(
            db_session,
            session.id,
            verdict="PASS",
            role="qa",
            task_id=str(uuid.uuid4()),
        )
        assert event.type == "verdict"
        assert event.data["verdict"] == "PASS"
        assert event.data["role"] == "qa"

    async def test_submit_with_all_fields(self, db_session: AsyncSession, session: SessionModel):
        tid = str(uuid.uuid4())
        event = await submit_verdict(
            db_session,
            session.id,
            verdict="FAIL",
            role="qa",
            task_id=tid,
            evidence=[{"type": "test_output", "content": "3 failed"}],
            criteria_results=[{"criterion": "Health 200", "result": "FAIL", "detail": "500 error"}],
            feedback="Tests are failing",
        )
        assert event.data["verdict"] == "FAIL"
        assert event.data["feedback"] == "Tests are failing"
        assert len(event.data["evidence"]) == 1
        assert len(event.data["criteria_results"]) == 1
        assert event.data["criteria_results"][0]["detail"] == "500 error"

    async def test_submit_invalid_verdict_raises(
        self, db_session: AsyncSession, session: SessionModel
    ):
        with pytest.raises(Exception):  # Pydantic ValidationError
            await submit_verdict(
                db_session,
                session.id,
                verdict="MAYBE",
                role="qa",
            )

    async def test_submit_invalid_session_raises(self, db_session: AsyncSession):
        fake_id = uuid.uuid4()
        with pytest.raises(ValueError, match="not found"):
            await submit_verdict(
                db_session,
                fake_id,
                verdict="PASS",
                role="qa",
            )


# ---------------------------------------------------------------------------
# Unit: get_verdict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetVerdict:
    async def test_get_existing_verdict(self, db_session: AsyncSession, session: SessionModel):
        await submit_verdict(
            db_session,
            session.id,
            verdict="PASS",
            role="qa",
        )
        result = await get_verdict(db_session, session.id)
        assert result is not None
        assert result["verdict"] == "PASS"

    async def test_get_no_verdict_returns_none(
        self, db_session: AsyncSession, session: SessionModel
    ):
        result = await get_verdict(db_session, session.id)
        assert result is None

    async def test_get_returns_most_recent(self, db_session: AsyncSession, session: SessionModel):
        # Submit two verdicts with explicitly different timestamps
        from codehive.db.models import Event as EventModel

        early = datetime(2026, 1, 1, 0, 0, 0)
        late = datetime(2026, 1, 1, 0, 0, 1)

        e1 = EventModel(
            session_id=session.id,
            type="verdict",
            data={"verdict": "FAIL", "role": "qa"},
            created_at=early,
        )
        db_session.add(e1)
        await db_session.commit()

        e2 = EventModel(
            session_id=session.id,
            type="verdict",
            data={"verdict": "PASS", "role": "qa"},
            created_at=late,
        )
        db_session.add(e2)
        await db_session.commit()

        result = await get_verdict(db_session, session.id)
        assert result is not None
        assert result["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# Unit: Orchestrator fallback logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorFallback:
    async def test_structured_verdict_used_when_available(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """When a child session has a structured verdict, parse_verdict is NOT called."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Structured verdict task",
            pipeline_status="backlog",
        )

        async def mock_spawn(task_id, step, role, mode, instructions):
            # Create a child session and submit a structured verdict
            async with db_session_factory() as db:
                child = SessionModel(
                    project_id=project.id,
                    name=f"{role}-{step}-{task_id}",
                    engine="claude_code",
                    mode=mode,
                    status="idle",
                    config={},
                    task_id=task_id,
                    pipeline_step=step,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(child)
                await db.commit()
                await db.refresh(child)

                if step in ("testing", "accepting"):
                    v = "PASS" if step == "testing" else "ACCEPT"
                    await submit_verdict(db, child.id, verdict=v, role=role)

            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            # For testing/accepting, no text verdict needed -- structured takes priority
            return "Agent finished."

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_fallback_to_parse_verdict_when_no_structured(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """When no structured verdict exists, falls back to regex parse_verdict."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Fallback task",
            pipeline_status="backlog",
        )

        async def mock_spawn(task_id, step, role, mode, instructions):
            # No child session with verdict -- just text
            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            elif step == "testing":
                return "All pass. VERDICT: PASS"
            elif step == "accepting":
                return "Good. VERDICT: ACCEPT"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_structured_reject_populates_feedback(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
    ):
        """Structured REJECT verdict populates StepResult.feedback."""
        orch_session.issue_id = issue.id
        await db_session.commit()

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Reject feedback task",
            pipeline_status="backlog",
        )

        call_count: dict[str, int] = {}

        async def mock_spawn(task_id, step, role, mode, instructions):
            call_count[step] = call_count.get(step, 0) + 1

            async with db_session_factory() as db:
                child = SessionModel(
                    project_id=project.id,
                    name=f"{role}-{step}-{task_id}-{call_count[step]}",
                    engine="claude_code",
                    mode=mode,
                    status="idle",
                    config={},
                    task_id=task_id,
                    pipeline_step=step,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(child)
                await db.commit()
                await db.refresh(child)

                if step == "testing":
                    if call_count["testing"] == 1:
                        await submit_verdict(
                            db,
                            child.id,
                            verdict="FAIL",
                            role="qa",
                            feedback="Health endpoint missing version field",
                            evidence=[{"type": "test_output", "content": "1 failed"}],
                            criteria_results=[
                                {
                                    "criterion": "Version present",
                                    "result": "FAIL",
                                    "detail": "missing",
                                }
                            ],
                        )
                        return "Agent done."
                    else:
                        await submit_verdict(db, child.id, verdict="PASS", role="qa")
                        return "Agent done."
                elif step == "accepting":
                    await submit_verdict(db, child.id, verdict="ACCEPT", role="pm")
                    return "Agent done."

            if step == "grooming":
                return "Groomed. VERDICT: PASS"
            elif step == "implementing":
                return "Implemented. VERDICT: PASS"
            return ""

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        await service._run_task_pipeline(task)

        # Task should complete
        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

        # QA was called twice, implementing was called twice (initial + fix after reject)
        assert call_count.get("testing", 0) == 2
        assert call_count.get("implementing", 0) == 2


# ---------------------------------------------------------------------------
# Integration: Evidence storage round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEvidenceStorage:
    async def test_evidence_items_round_trip(self, db_session: AsyncSession, session: SessionModel):
        evidence = [
            {"type": "test_output", "content": "12 passed, 0 failed"},
            {"type": "screenshot", "path": "/tmp/screenshot-001.png"},
            {"type": "log_excerpt", "content": "INFO: Server started"},
        ]
        await submit_verdict(
            db_session,
            session.id,
            verdict="PASS",
            role="qa",
            evidence=evidence,
        )
        result = await get_verdict(db_session, session.id)
        assert result is not None
        assert len(result["evidence"]) == 3
        assert result["evidence"][0]["content"] == "12 passed, 0 failed"
        assert result["evidence"][1]["path"] == "/tmp/screenshot-001.png"

    async def test_criteria_results_round_trip(
        self, db_session: AsyncSession, session: SessionModel
    ):
        criteria = [
            {"criterion": "Health endpoint returns 200", "result": "PASS"},
            {"criterion": "Version field present", "result": "FAIL", "detail": "missing"},
        ]
        await submit_verdict(
            db_session,
            session.id,
            verdict="FAIL",
            role="qa",
            criteria_results=criteria,
        )
        result = await get_verdict(db_session, session.id)
        assert result is not None
        assert len(result["criteria_results"]) == 2
        assert result["criteria_results"][0]["result"] == "PASS"
        assert result["criteria_results"][1]["detail"] == "missing"


# ---------------------------------------------------------------------------
# Unit: build_instructions includes submit_verdict guidance
# ---------------------------------------------------------------------------


class TestBuildInstructionsVerdictGuidance:
    def test_testing_instructions_mention_submit_verdict(self):
        text = build_instructions(
            "testing",
            "Test task",
            None,
            acceptance_criteria="- Pass tests",
        )
        assert "submit_verdict" in text

    def test_accepting_instructions_mention_submit_verdict(self):
        text = build_instructions(
            "accepting",
            "Accept task",
            None,
            acceptance_criteria="- Pass tests",
        )
        assert "submit_verdict" in text

    def test_implementing_instructions_no_submit_verdict(self):
        text = build_instructions(
            "implementing",
            "Implement task",
            "Do the work",
        )
        assert "submit_verdict" not in text


# ---------------------------------------------------------------------------
# Unit: StepResult new fields
# ---------------------------------------------------------------------------


class TestStepResultFields:
    def test_step_result_defaults(self):
        r = StepResult(verdict=Verdict.PASS)
        assert r.evidence is None
        assert r.criteria_results is None
        assert r.feedback is None

    def test_step_result_with_all_fields(self):
        r = StepResult(
            verdict=Verdict.FAIL,
            output="output text",
            session_id=uuid.uuid4(),
            evidence=[{"type": "test_output", "content": "3 failed"}],
            criteria_results=[{"criterion": "X", "result": "FAIL"}],
            feedback="Fix the tests",
        )
        assert r.feedback == "Fix the tests"
        assert len(r.evidence) == 1
        assert len(r.criteria_results) == 1
