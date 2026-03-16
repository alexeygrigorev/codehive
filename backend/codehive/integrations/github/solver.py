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
            return SolveResult(success=False, commit_sha=None, error=error_output)

        # 6. Tests passed -- commit and push
        issue_num = issue.github_issue_id or 0
        commit_msg = f"Fix #{issue_num}: {issue.title}"
        sha = await git_ops.commit(commit_msg)
        await git_ops.push()

        if session_row is not None:
            session_row.status = "completed"
            await db.commit()

        return SolveResult(success=True, commit_sha=sha, error=None)

    except Exception as exc:
        logger.exception("solve_issue failed for issue %s", issue_id)
        # Update session status to failed (best effort)
        try:
            session_row = await db.get(SessionModel, session_id)
            if session_row is not None:
                session_row.status = "failed"
                await db.commit()
        except Exception:
            pass
        return SolveResult(success=False, commit_sha=None, error=str(exc))
