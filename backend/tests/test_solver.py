"""Tests for GitHub solver orchestration and trigger integration."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.execution.git_ops import GitOps, GitOpsError
from codehive.execution.shell import ShellResult, ShellRunner
from codehive.integrations.github.solver import SolveResult, build_solver_prompt, solve_issue
from codehive.integrations.github.triggers import handle_issue_event
from codehive.integrations.github.webhook import WebhookEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    *,
    issue_id: uuid.UUID | None = None,
    title: str = "Fix login bug",
    description: str = "Users cannot log in when password contains special chars",
    github_issue_id: int = 42,
    project_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a mock Issue row."""
    issue = MagicMock()
    issue.id = issue_id or uuid.uuid4()
    issue.title = title
    issue.description = description
    issue.github_issue_id = github_issue_id
    issue.project_id = project_id or uuid.uuid4()
    return issue


def _make_project(
    *,
    project_id: uuid.UUID | None = None,
    knowledge: dict | None = None,
) -> MagicMock:
    """Return a mock Project row."""
    proj = MagicMock()
    proj.id = project_id or uuid.uuid4()
    proj.knowledge = knowledge if knowledge is not None else {}
    return proj


def _make_session_row(
    *,
    session_id: uuid.UUID | None = None,
    status: str = "idle",
) -> MagicMock:
    """Return a mock Session row."""
    row = MagicMock()
    row.id = session_id or uuid.uuid4()
    row.status = status
    return row


def _make_db(issue=None, project=None, session_row=None):
    """Build a mock AsyncSession whose .get() returns the right object per model class."""
    from codehive.db.models import Issue as IssueModel
    from codehive.db.models import Project as ProjectModel
    from codehive.db.models import Session as SessionModel

    async def _get(model, pk):
        if model is IssueModel:
            return issue
        if model is ProjectModel:
            return project
        if model is SessionModel:
            return session_row
        return None

    db = AsyncMock()
    db.get = AsyncMock(side_effect=_get)
    db.commit = AsyncMock()
    return db


def _make_engine():
    """Return a mock NativeEngine."""
    engine = AsyncMock()
    engine.create_session = AsyncMock()

    async def _send_message(*args, **kwargs):
        yield {"type": "message.created", "role": "assistant", "content": "done"}

    engine.send_message = MagicMock(side_effect=_send_message)
    return engine


def _make_git_ops(sha: str = "abc123") -> MagicMock:
    git_ops = AsyncMock(spec=GitOps)
    git_ops.commit = AsyncMock(return_value=sha)
    git_ops.push = AsyncMock(return_value="")
    git_ops._repo = Path("/tmp/repo")
    return git_ops


def _make_shell_runner(exit_code: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    runner = AsyncMock(spec=ShellRunner)
    runner.run = AsyncMock(
        return_value=ShellResult(exit_code=exit_code, stdout=stdout, stderr=stderr)
    )
    return runner


# ===========================================================================
# Unit: build_solver_prompt
# ===========================================================================


class TestBuildSolverPrompt:
    def test_contains_issue_number_title_description(self):
        prompt = build_solver_prompt(
            issue_title="Fix login bug",
            issue_description="Users cannot log in",
            github_issue_number=42,
        )
        assert "#42" in prompt
        assert "Fix login bug" in prompt
        assert "Users cannot log in" in prompt

    def test_includes_tech_stack_when_present(self):
        prompt = build_solver_prompt(
            issue_title="Add feature",
            issue_description="Add a new feature",
            github_issue_number=10,
            knowledge={"tech_stack": "Python 3.13, FastAPI, PostgreSQL"},
        )
        assert "Python 3.13" in prompt
        assert "Tech Stack" in prompt

    def test_no_tech_stack_when_knowledge_is_none(self):
        prompt = build_solver_prompt(
            issue_title="Bug",
            issue_description="A bug",
            github_issue_number=1,
            knowledge=None,
        )
        assert "Tech Stack" not in prompt
        # Should still have the basics
        assert "#1" in prompt
        assert "Bug" in prompt

    def test_no_tech_stack_when_knowledge_empty(self):
        prompt = build_solver_prompt(
            issue_title="Bug",
            issue_description="A bug",
            github_issue_number=1,
            knowledge={},
        )
        assert "Tech Stack" not in prompt


# ===========================================================================
# Unit: SolveResult dataclass
# ===========================================================================


class TestSolveResult:
    def test_success_with_sha(self):
        r = SolveResult(success=True, commit_sha="abc123", error=None)
        assert r.success is True
        assert r.commit_sha == "abc123"
        assert r.error is None

    def test_failure_with_error(self):
        r = SolveResult(success=False, commit_sha=None, error="tests failed")
        assert r.success is False
        assert r.commit_sha is None
        assert r.error == "tests failed"


# ===========================================================================
# Unit: solve_issue -- success path
# ===========================================================================


@pytest.mark.asyncio
class TestSolveIssueSuccess:
    async def test_success_path(self):
        issue = _make_issue()
        project = _make_project(project_id=issue.project_id)
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops(sha="def456")
        shell_runner = _make_shell_runner(exit_code=0, stdout="all tests passed")

        result = await solve_issue(
            db=db,
            project_id=project.id,
            issue_id=issue.id,
            session_id=session_row.id,
            engine=engine,
            git_ops=git_ops,
            shell_runner=shell_runner,
        )

        assert result.success is True
        assert result.commit_sha == "def456"
        assert result.error is None

        # engine.send_message was called with a prompt containing the issue title
        engine.send_message.assert_called_once()
        call_args = engine.send_message.call_args
        prompt_arg = call_args[0][1]  # second positional arg
        assert "Fix login bug" in prompt_arg

        # git_ops.commit was called with message containing issue number
        git_ops.commit.assert_awaited_once()
        commit_msg = git_ops.commit.call_args[0][0]
        assert "#42" in commit_msg

        # git_ops.push was called
        git_ops.push.assert_awaited_once()

        # session status updated to completed
        assert session_row.status == "completed"


# ===========================================================================
# Unit: solve_issue -- test failure path
# ===========================================================================


@pytest.mark.asyncio
class TestSolveIssueTestFailure:
    async def test_failure_no_commit(self):
        issue = _make_issue()
        project = _make_project(project_id=issue.project_id)
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner(
            exit_code=1, stdout="FAILED test_login", stderr="AssertionError"
        )

        result = await solve_issue(
            db=db,
            project_id=project.id,
            issue_id=issue.id,
            session_id=session_row.id,
            engine=engine,
            git_ops=git_ops,
            shell_runner=shell_runner,
        )

        assert result.success is False
        assert "FAILED test_login" in result.error
        assert result.commit_sha is None

        # commit and push were NOT called
        git_ops.commit.assert_not_awaited()
        git_ops.push.assert_not_awaited()

        # session status is failed
        assert session_row.status == "failed"


# ===========================================================================
# Unit: solve_issue -- engine exception path
# ===========================================================================


@pytest.mark.asyncio
class TestSolveIssueEngineException:
    async def test_engine_exception(self):
        issue = _make_issue()
        project = _make_project(project_id=issue.project_id)
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)

        engine = AsyncMock()
        engine.create_session = AsyncMock()

        async def _exploding_send(*args, **kwargs):
            raise RuntimeError("API rate limit exceeded")
            yield  # make it an async generator  # noqa: RUF027

        engine.send_message = MagicMock(side_effect=_exploding_send)

        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner()

        result = await solve_issue(
            db=db,
            project_id=project.id,
            issue_id=issue.id,
            session_id=session_row.id,
            engine=engine,
            git_ops=git_ops,
            shell_runner=shell_runner,
        )

        assert result.success is False
        assert "API rate limit exceeded" in result.error
        assert result.commit_sha is None

        git_ops.commit.assert_not_awaited()
        git_ops.push.assert_not_awaited()


# ===========================================================================
# Unit: solve_issue -- issue not found
# ===========================================================================


@pytest.mark.asyncio
class TestSolveIssueNotFound:
    async def test_issue_not_found(self):
        db = _make_db(issue=None, project=None, session_row=_make_session_row())
        engine = _make_engine()
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner()

        issue_id = uuid.uuid4()
        result = await solve_issue(
            db=db,
            project_id=uuid.uuid4(),
            issue_id=issue_id,
            session_id=uuid.uuid4(),
            engine=engine,
            git_ops=git_ops,
            shell_runner=shell_runner,
        )

        assert result.success is False
        assert "not found" in result.error


# ===========================================================================
# Unit: GitOps.push
# ===========================================================================


@pytest.mark.asyncio
class TestGitOpsPush:
    async def test_push_success(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"Everything up-to-date\n", b""))
            proc.returncode = 0
            mock_exec.return_value = proc

            ops = GitOps(Path("/tmp/repo"))
            result = await ops.push("origin", "main")

            assert "Everything up-to-date" in result
            mock_exec.assert_called_once_with(
                "git",
                "push",
                "origin",
                "main",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path("/tmp/repo"),
            )

    async def test_push_failure_raises(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"", b"rejected\n"))
            proc.returncode = 1
            mock_exec.return_value = proc

            ops = GitOps(Path("/tmp/repo"))
            with pytest.raises(GitOpsError, match="rejected"):
                await ops.push()


# ===========================================================================
# Integration: trigger launches solver in auto mode
# ===========================================================================


def _gh_webhook_payload(
    *,
    action: str = "opened",
    number: int = 42,
    title: str = "Fix login bug",
    body: str = "Description of the bug",
) -> dict:
    return {
        "action": action,
        "issue": {
            "number": number,
            "title": title,
            "body": body,
            "state": "open",
            "labels": [],
        },
        "repository": {
            "name": "Hello-World",
            "owner": {"login": "octocat"},
        },
    }


@pytest.mark.asyncio
class TestTriggerLaunchesSolver:
    async def test_auto_mode_launches_solver(self, tmp_path):
        """When trigger_mode is auto and action is opened, solve_issue is launched as a task."""
        from datetime import datetime, timezone

        from sqlalchemy import JSON, MetaData, event, text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from codehive.db.models import Base, Project

        # Set up in-memory SQLite
        engine_db = create_async_engine("sqlite+aiosqlite:///:memory:")

        @event.listens_for(engine_db.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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
            from sqlalchemy import Table

            Table(table.name, metadata, *columns)

        async with engine_db.begin() as conn:
            await conn.run_sync(metadata.create_all)

        session_factory = async_sessionmaker(engine_db, expire_on_commit=False)
        async with session_factory() as db:
            proj = Project(
                name="test",
                knowledge={},
                created_at=datetime.now(timezone.utc),
            )
            db.add(proj)
            await db.commit()
            await db.refresh(proj)

            webhook_event = WebhookEvent(
                event_type="issues",
                action="opened",
                payload=_gh_webhook_payload(),
            )

            solver_called = False

            async def _mock_solve(**kwargs):
                nonlocal solver_called
                solver_called = True
                return SolveResult(success=True, commit_sha="abc", error=None)

            mock_engine = _make_engine()
            mock_git_ops = _make_git_ops()
            mock_shell_runner = _make_shell_runner()

            solver_deps = {
                "db": db,
                "engine": mock_engine,
                "git_ops": mock_git_ops,
                "shell_runner": mock_shell_runner,
            }

            with patch("codehive.integrations.github.triggers.solve_issue", new=_mock_solve):
                result = await handle_issue_event(
                    db, proj.id, webhook_event, "auto", solver_deps=solver_deps
                )

            assert result.action_taken == "session_created"
            assert result.session_id is not None

            # Give the background task a chance to run
            await asyncio.sleep(0.05)
            assert solver_called

        await engine_db.dispose()

    async def test_manual_mode_does_not_launch_solver(self, tmp_path):
        """When trigger_mode is manual, solve_issue is NOT called."""
        from datetime import datetime, timezone

        from sqlalchemy import JSON, MetaData, event, text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from codehive.db.models import Base, Project

        engine_db = create_async_engine("sqlite+aiosqlite:///:memory:")

        @event.listens_for(engine_db.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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
            from sqlalchemy import Table

            Table(table.name, metadata, *columns)

        async with engine_db.begin() as conn:
            await conn.run_sync(metadata.create_all)

        session_factory = async_sessionmaker(engine_db, expire_on_commit=False)
        async with session_factory() as db:
            proj = Project(
                name="test",
                knowledge={},
                created_at=datetime.now(timezone.utc),
            )
            db.add(proj)
            await db.commit()
            await db.refresh(proj)

            webhook_event = WebhookEvent(
                event_type="issues",
                action="opened",
                payload=_gh_webhook_payload(),
            )

            solver_called = False

            async def _mock_solve(**kwargs):
                nonlocal solver_called
                solver_called = True
                return SolveResult(success=True, commit_sha="abc", error=None)

            with patch("codehive.integrations.github.triggers.solve_issue", new=_mock_solve):
                result = await handle_issue_event(db, proj.id, webhook_event, "manual")

            assert result.action_taken == "imported"
            await asyncio.sleep(0.05)
            assert not solver_called

        await engine_db.dispose()

    async def test_suggest_mode_does_not_launch_solver(self, tmp_path):
        """When trigger_mode is suggest, solve_issue is NOT called."""
        from datetime import datetime, timezone

        from sqlalchemy import JSON, MetaData, event, text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from codehive.db.models import Base, Project

        engine_db = create_async_engine("sqlite+aiosqlite:///:memory:")

        @event.listens_for(engine_db.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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
            from sqlalchemy import Table

            Table(table.name, metadata, *columns)

        async with engine_db.begin() as conn:
            await conn.run_sync(metadata.create_all)

        session_factory = async_sessionmaker(engine_db, expire_on_commit=False)
        async with session_factory() as db:
            proj = Project(
                name="test",
                knowledge={},
                created_at=datetime.now(timezone.utc),
            )
            db.add(proj)
            await db.commit()
            await db.refresh(proj)

            webhook_event = WebhookEvent(
                event_type="issues",
                action="opened",
                payload=_gh_webhook_payload(),
            )

            solver_called = False

            async def _mock_solve(**kwargs):
                nonlocal solver_called
                solver_called = True
                return SolveResult(success=True, commit_sha="abc", error=None)

            with patch("codehive.integrations.github.triggers.solve_issue", new=_mock_solve):
                result = await handle_issue_event(db, proj.id, webhook_event, "suggest")

            assert result.action_taken == "suggested"
            await asyncio.sleep(0.05)
            assert not solver_called

        await engine_db.dispose()


# ===========================================================================
# Unit: solve_issue uses test_command from knowledge
# ===========================================================================


@pytest.mark.asyncio
class TestSolveIssueTestCommand:
    async def test_uses_knowledge_test_command(self):
        """When knowledge has test_command, solver uses it instead of default pytest."""
        issue = _make_issue()
        project = _make_project(
            project_id=issue.project_id,
            knowledge={"test_command": "npm test"},
        )
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner(exit_code=0)

        await solve_issue(
            db=db,
            project_id=project.id,
            issue_id=issue.id,
            session_id=session_row.id,
            engine=engine,
            git_ops=git_ops,
            shell_runner=shell_runner,
        )

        # shell_runner.run was called with "npm test"
        shell_runner.run.assert_awaited_once()
        cmd_arg = shell_runner.run.call_args[0][0]
        assert cmd_arg == "npm test"
