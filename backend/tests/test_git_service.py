"""Tests for GitService -- uses real temporary git repos via tmp_path."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.core.git_service import GitError, GitService
from codehive.core.issues import create_issue, list_issue_log_entries
from codehive.core.orchestrator_service import OrchestratorService
from codehive.core.task_queue import create_task
from codehive.db.models import Base, Project, Task
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _init_repo(path: Path) -> None:
    """Initialise a bare-bones git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True
    )
    # Create an initial commit so HEAD exists
    (path / "README.md").write_text("# init\n")
    subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=path, capture_output=True, check=True
    )


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
async def db_session(db_session_factory):
    async with db_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Unit: repo_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRepoStatus:
    async def test_valid_repo(self, tmp_path: Path):
        _init_repo(tmp_path)
        status = await GitService.repo_status(str(tmp_path))
        assert status["branch"] in ("main", "master")
        assert status["dirty_count"] == 0
        assert SHA_RE.match(status["last_sha"])

    async def test_not_a_git_repo(self, tmp_path: Path):
        with pytest.raises(GitError, match="Not a git repository"):
            await GitService.repo_status(str(tmp_path))


# ---------------------------------------------------------------------------
# Unit: stage_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStageAll:
    async def test_stages_new_and_modified(self, tmp_path: Path):
        _init_repo(tmp_path)
        (tmp_path / "new_file.txt").write_text("hello")
        (tmp_path / "README.md").write_text("# modified\n")

        await GitService.stage_all(str(tmp_path))

        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=tmp_path,
            capture_output=True,
        )
        staged = result.stdout.decode().strip().splitlines()
        assert "new_file.txt" in staged
        assert "README.md" in staged


# ---------------------------------------------------------------------------
# Unit: commit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCommit:
    async def test_commit_returns_sha(self, tmp_path: Path):
        _init_repo(tmp_path)
        (tmp_path / "file.txt").write_text("content")
        await GitService.stage_all(str(tmp_path))

        sha = await GitService.commit(str(tmp_path), "Add file")
        assert SHA_RE.match(sha)

    async def test_commit_nothing_to_commit_raises(self, tmp_path: Path):
        _init_repo(tmp_path)
        with pytest.raises(GitError, match="git commit failed"):
            await GitService.commit(str(tmp_path), "Empty commit")


# ---------------------------------------------------------------------------
# Unit: push
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPush:
    async def test_push_no_remote_raises(self, tmp_path: Path):
        _init_repo(tmp_path)
        with pytest.raises(GitError, match="git push failed"):
            await GitService.push(str(tmp_path))


# ---------------------------------------------------------------------------
# Unit: commit_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCommitTask:
    async def test_commit_task_creates_conventional_commit(self, tmp_path: Path):
        _init_repo(tmp_path)
        (tmp_path / "feature.py").write_text("print('hello')\n")

        project = SimpleNamespace(path=str(tmp_path), github_config=None)
        task = SimpleNamespace(id=42, title="Add greeting feature")

        sha = await GitService.commit_task(project, task)
        assert SHA_RE.match(sha)

        # Verify commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=tmp_path, capture_output=True
        )
        msg = result.stdout.decode().strip()
        assert msg == "Implement task #42: Add greeting feature"

    async def test_commit_task_no_path_raises(self):
        project = SimpleNamespace(path=None, github_config=None)
        task = SimpleNamespace(id=1, title="Task")

        with pytest.raises(GitError, match="no local path"):
            await GitService.commit_task(project, task)

    async def test_commit_task_auto_push_true_attempts_push(self, tmp_path: Path):
        _init_repo(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")

        project = SimpleNamespace(path=str(tmp_path), github_config={"auto_push": True})
        task = SimpleNamespace(id=5, title="Feature")

        # Push will fail because there's no remote, but it should attempt it
        with pytest.raises(GitError, match="git push failed"):
            await GitService.commit_task(project, task)

    async def test_commit_task_auto_push_false_skips_push(self, tmp_path: Path):
        _init_repo(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")

        project = SimpleNamespace(path=str(tmp_path), github_config={"auto_push": False})
        task = SimpleNamespace(id=6, title="Feature")

        sha = await GitService.commit_task(project, task)
        assert SHA_RE.match(sha)

    async def test_commit_task_no_github_config_skips_push(self, tmp_path: Path):
        _init_repo(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")

        project = SimpleNamespace(path=str(tmp_path), github_config=None)
        task = SimpleNamespace(id=7, title="Feature")

        sha = await GitService.commit_task(project, task)
        assert SHA_RE.match(sha)


# ---------------------------------------------------------------------------
# Unit: Orchestrator git integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorGitIntegration:
    async def test_done_calls_git_commit(
        self,
        db_session_factory,
        db_session: AsyncSession,
    ):
        """When orchestrator transitions to done, GitService.commit_task is called."""
        project = Project(
            name="test-project",
            path="/tmp/fake",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Test Issue",
            description="desc",
        )

        orch_session = SessionModel(
            project_id=project.id,
            issue_id=issue.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(orch_session)
        await db_session.commit()
        await db_session.refresh(orch_session)

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Git test task",
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

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        with patch.object(GitService, "commit_task", new_callable=AsyncMock) as mock_commit:
            mock_commit.return_value = "abc123def456" + "0" * 28
            await service._run_task_pipeline(task)

            mock_commit.assert_called_once()
            call_args = mock_commit.call_args
            # First positional arg is project, second is task
            assert call_args[0][0].id == project.id
            assert call_args[0][1].id == task.id

    async def test_git_failure_does_not_block_done(
        self,
        db_session_factory,
        db_session: AsyncSession,
    ):
        """GitError does not prevent task from reaching done status."""
        project = Project(
            name="test-project",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Test Issue",
            description="desc",
        )

        orch_session = SessionModel(
            project_id=project.id,
            issue_id=issue.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(orch_session)
        await db_session.commit()
        await db_session.refresh(orch_session)

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Git fail task",
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

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        with patch.object(GitService, "commit_task", new_callable=AsyncMock) as mock_commit:
            mock_commit.side_effect = GitError("Project has no local path configured")
            await service._run_task_pipeline(task)

        # Task should still be done
        async with db_session_factory() as db:
            refreshed = await db.get(Task, task.id)
            assert refreshed.pipeline_status == "done"

    async def test_git_commit_sha_logged(
        self,
        db_session_factory,
        db_session: AsyncSession,
    ):
        """On successful commit, SHA is logged to the issue log."""
        project = Project(
            name="test-project",
            path="/tmp/fake",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Test Issue",
            description="desc",
        )

        orch_session = SessionModel(
            project_id=project.id,
            issue_id=issue.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(orch_session)
        await db_session.commit()
        await db_session.refresh(orch_session)

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="SHA log task",
            pipeline_status="backlog",
        )

        fake_sha = "a" * 40

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

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        with patch.object(GitService, "commit_task", new_callable=AsyncMock) as mock_commit:
            mock_commit.return_value = fake_sha
            await service._run_task_pipeline(task)

        async with db_session_factory() as db:
            logs = await list_issue_log_entries(db, issue.id)
            log_contents = [log.content for log in logs]
            assert any(fake_sha in c for c in log_contents)

    async def test_git_error_logged(
        self,
        db_session_factory,
        db_session: AsyncSession,
    ):
        """On git failure, error message is logged to the issue log."""
        project = Project(
            name="test-project",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Test Issue",
            description="desc",
        )

        orch_session = SessionModel(
            project_id=project.id,
            issue_id=issue.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(orch_session)
        await db_session.commit()
        await db_session.refresh(orch_session)

        task = await create_task(
            db_session,
            session_id=orch_session.id,
            title="Error log task",
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

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = mock_spawn

        with patch.object(GitService, "commit_task", new_callable=AsyncMock) as mock_commit:
            mock_commit.side_effect = GitError("No local path configured")
            await service._run_task_pipeline(task)

        async with db_session_factory() as db:
            logs = await list_issue_log_entries(db, issue.id)
            log_contents = [log.content for log in logs]
            assert any("Git commit failed" in c for c in log_contents)


# ---------------------------------------------------------------------------
# Integration: End-to-end with temp git repo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEndToEnd:
    async def test_e2e_commit_task_with_real_repo(self, tmp_path: Path):
        """Full flow: create temp repo, add file, commit_task, verify git log."""
        _init_repo(tmp_path)
        (tmp_path / "feature.py").write_text("def greet():\n    return 'hello'\n")

        project = SimpleNamespace(path=str(tmp_path), github_config=None)
        task = SimpleNamespace(id=99, title="Add greet function")

        sha = await GitService.commit_task(project, task)

        assert SHA_RE.match(sha)

        # Verify via git log
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=tmp_path, capture_output=True
        )
        msg = result.stdout.decode().strip()
        assert msg == "Implement task #99: Add greet function"

        # Verify the file is committed
        result = subprocess.run(
            ["git", "show", "--name-only", "--format="], cwd=tmp_path, capture_output=True
        )
        files = result.stdout.decode().strip()
        assert "feature.py" in files
