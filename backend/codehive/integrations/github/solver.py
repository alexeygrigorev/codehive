"""Solver orchestration: run the engine to solve a GitHub issue, test, commit, push."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Issue, Project, Session as SessionModel
from codehive.engine.native import NativeEngine
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner
from codehive.integrations.github.closer import close_github_issue, comment_failure

logger = logging.getLogger(__name__)


@dataclass
class SolveResult:
    """Outcome of a solve attempt."""

    success: bool
    commit_sha: str | None
    error: str | None


def build_solver_prompt(
    issue_title: str,
    issue_description: str,
    github_issue_number: int,
    knowledge: dict[str, Any] | None = None,
) -> str:
    """Build the prompt sent to the engine to solve a GitHub issue.

    The prompt includes the issue number, title, description, and optionally
    project tech-stack information from the knowledge dict.
    """
    parts: list[str] = [
        f"Solve GitHub issue #{github_issue_number}: {issue_title}",
        "",
        "## Issue Description",
        issue_description or "(no description provided)",
    ]

    if knowledge and knowledge.get("tech_stack"):
        parts.append("")
        parts.append("## Project Tech Stack")
        parts.append(str(knowledge["tech_stack"]))

    parts.append("")
    parts.append(
        "Implement the fix or feature described above. "
        "Write clean code and make sure existing tests still pass."
    )

    return "\n".join(parts)


def _github_config(knowledge: dict[str, Any] | None) -> tuple[str, str, str] | None:
    """Extract (owner, repo, token) from project knowledge, or None if missing."""
    if not knowledge:
        return None
    owner = knowledge.get("github_owner")
    repo = knowledge.get("github_repo")
    token = knowledge.get("github_token")
    if owner and repo and token:
        return (owner, repo, token)
    return None


async def _try_close_issue(
    owner: str,
    repo: str,
    issue_number: int,
    commit_sha: str,
    token: str,
) -> None:
    """Call close_github_issue, logging and swallowing any exception."""
    try:
        await close_github_issue(owner, repo, issue_number, commit_sha, token)
    except Exception:
        logger.exception("Failed to close GitHub issue %s/%s#%d", owner, repo, issue_number)


async def _try_comment_failure(
    owner: str,
    repo: str,
    issue_number: int,
    error_details: str,
    token: str,
) -> None:
    """Call comment_failure, logging and swallowing any exception."""
    try:
        await comment_failure(owner, repo, issue_number, error_details, token)
    except Exception:
        logger.exception(
            "Failed to comment failure on GitHub issue %s/%s#%d",
            owner,
            repo,
            issue_number,
        )


async def solve_issue(
    db: AsyncSession,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    session_id: uuid.UUID,
    engine: NativeEngine,
    git_ops: GitOps,
    shell_runner: ShellRunner,
    test_command: str | None = None,
) -> SolveResult:
    """Run the full solve pipeline for one GitHub issue.

    Steps:
      1. Load issue and project from DB.
      2. Compose a solver prompt.
      3. Initialise the engine session and send the prompt.
      4. Run tests via shell_runner.
      5. On success: commit and push.  On failure: report error.

    Returns a SolveResult describing the outcome.
    """
    try:
        # 1. Load the issue
        issue = await db.get(Issue, issue_id)
        if issue is None:
            return SolveResult(success=False, commit_sha=None, error=f"Issue {issue_id} not found")

        # Load the project (for knowledge / tech stack)
        project = await db.get(Project, project_id)

        # 2. Compose prompt
        knowledge = project.knowledge if project is not None else None
        prompt = build_solver_prompt(
            issue_title=issue.title,
            issue_description=issue.description or "",
            github_issue_number=issue.github_issue_id or 0,
            knowledge=knowledge,
        )

        # 3. Update session status to executing
        session_row = await db.get(SessionModel, session_id)
        if session_row is not None:
            session_row.status = "executing"
            await db.commit()

        # 4. Initialise engine session and send prompt
        await engine.create_session(session_id)
        async for _event in engine.send_message(session_id, prompt, db=db):
            pass  # consume all events until the generator is exhausted

        # 5. Run tests
        effective_test_cmd = test_command
        if effective_test_cmd is None and knowledge and knowledge.get("test_command"):
            effective_test_cmd = knowledge["test_command"]
        if effective_test_cmd is None:
            effective_test_cmd = "pytest"

        from pathlib import Path

        working_dir = git_ops._repo if hasattr(git_ops, "_repo") else Path(".")
        test_result = await shell_runner.run(effective_test_cmd, working_dir=working_dir)

        if test_result.exit_code != 0:
            # Tests failed -- do NOT commit
            error_output = test_result.stdout
            if test_result.stderr:
                error_output += "\n" + test_result.stderr
            if session_row is not None:
                session_row.status = "failed"
                await db.commit()
            # Comment failure on GitHub issue (best-effort)
            gh = _github_config(knowledge)
            if gh and issue.github_issue_id:
                await _try_comment_failure(gh[0], gh[1], issue.github_issue_id, error_output, gh[2])
            return SolveResult(success=False, commit_sha=None, error=error_output)

        # 6. Tests passed -- commit and push
        issue_num = issue.github_issue_id or 0
        commit_msg = f"Fix #{issue_num}: {issue.title}"
        sha = await git_ops.commit(commit_msg)
        await git_ops.push()

        # Close GitHub issue (best-effort)
        gh = _github_config(knowledge)
        if gh and issue.github_issue_id:
            await _try_close_issue(gh[0], gh[1], issue.github_issue_id, sha, gh[2])

        # Update internal issue status to closed
        issue.status = "closed"

        if session_row is not None:
            session_row.status = "completed"
            await db.commit()

        return SolveResult(success=True, commit_sha=sha, error=None)

    except Exception as exc:
        logger.exception("solve_issue failed for issue %s", issue_id)
        # Comment failure on GitHub issue (best-effort)
        try:
            _project = await db.get(Project, project_id)
            _knowledge = _project.knowledge if _project is not None else None
            gh = _github_config(_knowledge)
            _issue = await db.get(Issue, issue_id)
            if gh and _issue and _issue.github_issue_id:
                await _try_comment_failure(gh[0], gh[1], _issue.github_issue_id, str(exc), gh[2])
        except Exception:
            pass
        # Update session status to failed (best effort)
        try:
            session_row = await db.get(SessionModel, session_id)
            if session_row is not None:
                session_row.status = "failed"
                await db.commit()
        except Exception:
            pass
        return SolveResult(success=False, commit_sha=None, error=str(exc))
