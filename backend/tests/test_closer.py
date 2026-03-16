"""Tests for GitHub issue closer and solver integration."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from codehive.execution.shell import ShellResult
from codehive.integrations.github.client import GitHubAPIError
from codehive.integrations.github.closer import close_github_issue, comment_failure
from codehive.integrations.github.solver import solve_issue


# ---------------------------------------------------------------------------
# Helpers (shared with test_solver.py patterns)
# ---------------------------------------------------------------------------

OWNER = "octocat"
REPO = "hello-world"
TOKEN = "ghp_test_token"
ISSUE_NUM = 42
SHA = "abc123def"


def _make_issue(
    *,
    issue_id: uuid.UUID | None = None,
    title: str = "Fix login bug",
    description: str = "Users cannot log in",
    github_issue_id: int = ISSUE_NUM,
    project_id: uuid.UUID | None = None,
    status: str = "open",
) -> MagicMock:
    issue = MagicMock()
    issue.id = issue_id or uuid.uuid4()
    issue.title = title
    issue.description = description
    issue.github_issue_id = github_issue_id
    issue.project_id = project_id or uuid.uuid4()
    issue.status = status
    return issue


def _make_project(
    *,
    project_id: uuid.UUID | None = None,
    knowledge: dict | None = None,
) -> MagicMock:
    proj = MagicMock()
    proj.id = project_id or uuid.uuid4()
    proj.knowledge = knowledge if knowledge is not None else {}
    return proj


def _github_knowledge() -> dict:
    return {
        "github_owner": OWNER,
        "github_repo": REPO,
        "github_token": TOKEN,
    }


def _make_session_row(*, session_id: uuid.UUID | None = None, status: str = "idle") -> MagicMock:
    row = MagicMock()
    row.id = session_id or uuid.uuid4()
    row.status = status
    return row


def _make_db(issue=None, project=None, session_row=None):
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
    engine = AsyncMock()
    engine.create_session = AsyncMock()

    async def _send_message(*args, **kwargs):
        yield {"type": "message.created", "role": "assistant", "content": "done"}

    engine.send_message = MagicMock(side_effect=_send_message)
    return engine


def _make_git_ops(sha: str = SHA) -> MagicMock:
    from codehive.execution.git_ops import GitOps

    git_ops = AsyncMock(spec=GitOps)
    git_ops.commit = AsyncMock(return_value=sha)
    git_ops.push = AsyncMock(return_value="")
    git_ops._repo = Path("/tmp/repo")
    return git_ops


def _make_shell_runner(exit_code: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    from codehive.execution.shell import ShellRunner

    runner = AsyncMock(spec=ShellRunner)
    runner.run = AsyncMock(
        return_value=ShellResult(exit_code=exit_code, stdout=stdout, stderr=stderr)
    )
    return runner


def _mock_response(status_code: int, json_data: dict | None = None) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "https://api.github.com/test"),
    )
    return resp


# ===========================================================================
# Unit: close_github_issue -- success
# ===========================================================================


@pytest.mark.asyncio
class TestCloseGithubIssueSuccess:
    async def test_posts_comment_and_patches_state(self):
        """close_github_issue POSTs a comment with SHA and PATCHes state to closed."""
        calls: list[tuple[str, str, dict]] = []

        async def _mock_request(self, method, url, **kwargs):
            calls.append((method, url, kwargs.get("json", {})))
            return _mock_response(201 if method == "POST" else 200)

        with (
            patch.object(httpx.AsyncClient, "post", autospec=True) as mock_post,
            patch.object(httpx.AsyncClient, "patch", autospec=True) as mock_patch,
        ):
            mock_post.return_value = _mock_response(201, {"id": 1})
            mock_patch.return_value = _mock_response(200, {"state": "closed"})

            await close_github_issue(OWNER, REPO, ISSUE_NUM, SHA, TOKEN)

            # POST was called with body containing commit SHA
            post_call = mock_post.call_args
            assert SHA in post_call.kwargs.get("json", post_call[1].get("json", {}))["body"]

            # PATCH was called with state: closed
            patch_call = mock_patch.call_args
            patch_json = patch_call.kwargs.get("json", patch_call[1].get("json", {}))
            assert patch_json == {"state": "closed"}


# ===========================================================================
# Unit: close_github_issue -- API error
# ===========================================================================


@pytest.mark.asyncio
class TestCloseGithubIssueError:
    async def test_raises_on_non_2xx(self):
        """close_github_issue raises GitHubAPIError when POST returns 403."""
        with patch.object(httpx.AsyncClient, "post", autospec=True) as mock_post:
            mock_post.return_value = _mock_response(403, {"message": "forbidden"})

            with pytest.raises(GitHubAPIError) as exc_info:
                await close_github_issue(OWNER, REPO, ISSUE_NUM, SHA, TOKEN)

            assert exc_info.value.status_code == 403


# ===========================================================================
# Unit: comment_failure -- success
# ===========================================================================


@pytest.mark.asyncio
class TestCommentFailureSuccess:
    async def test_posts_comment_no_patch(self):
        """comment_failure POSTs error details and does NOT PATCH the issue."""
        error_msg = "tests failed: 3 errors"

        with (
            patch.object(httpx.AsyncClient, "post", autospec=True) as mock_post,
            patch.object(httpx.AsyncClient, "patch", autospec=True) as mock_patch,
        ):
            mock_post.return_value = _mock_response(201, {"id": 2})

            await comment_failure(OWNER, REPO, ISSUE_NUM, error_msg, TOKEN)

            # POST was called with body containing the error details
            post_call = mock_post.call_args
            post_body = post_call.kwargs.get("json", post_call[1].get("json", {}))["body"]
            assert error_msg in post_body

            # PATCH was NOT called (issue stays open)
            mock_patch.assert_not_called()


# ===========================================================================
# Unit: comment_failure -- API error
# ===========================================================================


@pytest.mark.asyncio
class TestCommentFailureError:
    async def test_raises_on_non_2xx(self):
        """comment_failure raises GitHubAPIError when POST returns 500."""
        with patch.object(httpx.AsyncClient, "post", autospec=True) as mock_post:
            mock_post.return_value = _mock_response(500, {"message": "server error"})

            with pytest.raises(GitHubAPIError) as exc_info:
                await comment_failure(OWNER, REPO, ISSUE_NUM, "some error", TOKEN)

            assert exc_info.value.status_code == 500


# ===========================================================================
# Integration: solver calls close_github_issue on success
# ===========================================================================


@pytest.mark.asyncio
class TestSolverCallsCloseOnSuccess:
    async def test_close_called_with_correct_args(self):
        issue = _make_issue()
        project = _make_project(
            project_id=issue.project_id,
            knowledge=_github_knowledge(),
        )
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops(sha="def456")
        shell_runner = _make_shell_runner(exit_code=0, stdout="all tests passed")

        with patch(
            "codehive.integrations.github.solver.close_github_issue", new_callable=AsyncMock
        ) as mock_close:
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

            mock_close.assert_awaited_once_with(OWNER, REPO, ISSUE_NUM, "def456", TOKEN)


# ===========================================================================
# Integration: solver calls comment_failure on test failure
# ===========================================================================


@pytest.mark.asyncio
class TestSolverCallsCommentOnTestFailure:
    async def test_comment_failure_called_close_not_called(self):
        issue = _make_issue()
        project = _make_project(
            project_id=issue.project_id,
            knowledge=_github_knowledge(),
        )
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner(
            exit_code=1, stdout="FAILED test_login", stderr="AssertionError"
        )

        with (
            patch(
                "codehive.integrations.github.solver.comment_failure", new_callable=AsyncMock
            ) as mock_comment,
            patch(
                "codehive.integrations.github.solver.close_github_issue", new_callable=AsyncMock
            ) as mock_close,
        ):
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

            # comment_failure was called with error details
            mock_comment.assert_awaited_once()
            call_args = mock_comment.call_args
            assert "FAILED test_login" in call_args[0][3]  # error_details arg

            # close_github_issue was NOT called
            mock_close.assert_not_awaited()


# ===========================================================================
# Integration: solver calls comment_failure on engine exception
# ===========================================================================


@pytest.mark.asyncio
class TestSolverCallsCommentOnEngineException:
    async def test_comment_failure_on_engine_crash(self):
        issue = _make_issue()
        project = _make_project(
            project_id=issue.project_id,
            knowledge=_github_knowledge(),
        )
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)

        engine = AsyncMock()
        engine.create_session = AsyncMock()

        async def _exploding_send(*args, **kwargs):
            raise RuntimeError("engine crashed")
            yield  # noqa: RUF027

        engine.send_message = MagicMock(side_effect=_exploding_send)
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner()

        with (
            patch(
                "codehive.integrations.github.solver.comment_failure", new_callable=AsyncMock
            ) as mock_comment,
            patch(
                "codehive.integrations.github.solver.close_github_issue", new_callable=AsyncMock
            ) as mock_close,
        ):
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
            assert "engine crashed" in result.error

            # comment_failure was called
            mock_comment.assert_awaited_once()
            call_args = mock_comment.call_args
            assert "engine crashed" in call_args[0][3]

            # close was NOT called
            mock_close.assert_not_awaited()


# ===========================================================================
# Integration: closer failure does not crash solver
# ===========================================================================


@pytest.mark.asyncio
class TestCloserFailureDoesNotCrashSolver:
    async def test_solver_succeeds_even_if_closer_fails(self):
        issue = _make_issue()
        project = _make_project(
            project_id=issue.project_id,
            knowledge=_github_knowledge(),
        )
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops(sha="def456")
        shell_runner = _make_shell_runner(exit_code=0)

        with (
            patch(
                "codehive.integrations.github.solver.close_github_issue", new_callable=AsyncMock
            ) as mock_close,
            patch("codehive.integrations.github.solver.logger") as mock_logger,
        ):
            mock_close.side_effect = GitHubAPIError(502, "bad gateway")

            result = await solve_issue(
                db=db,
                project_id=project.id,
                issue_id=issue.id,
                session_id=session_row.id,
                engine=engine,
                git_ops=git_ops,
                shell_runner=shell_runner,
            )

            # Solver still returns success
            assert result.success is True
            assert result.commit_sha == "def456"

            # Error was logged
            mock_logger.exception.assert_called()


# ===========================================================================
# Unit: internal issue status updated
# ===========================================================================


@pytest.mark.asyncio
class TestIssueStatusUpdate:
    async def test_success_sets_status_closed(self):
        issue = _make_issue(status="open")
        project = _make_project(project_id=issue.project_id, knowledge=_github_knowledge())
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner(exit_code=0)

        with patch(
            "codehive.integrations.github.solver.close_github_issue", new_callable=AsyncMock
        ):
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
        assert issue.status == "closed"

    async def test_failure_keeps_status_open(self):
        issue = _make_issue(status="open")
        project = _make_project(project_id=issue.project_id, knowledge=_github_knowledge())
        session_row = _make_session_row()
        db = _make_db(issue=issue, project=project, session_row=session_row)
        engine = _make_engine()
        git_ops = _make_git_ops()
        shell_runner = _make_shell_runner(exit_code=1, stdout="tests failed")

        with patch("codehive.integrations.github.solver.comment_failure", new_callable=AsyncMock):
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
        assert issue.status == "open"
