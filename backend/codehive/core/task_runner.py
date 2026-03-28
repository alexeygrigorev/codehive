"""Deterministic task execution runner -- drives a single task through the pipeline.

Extracted from OrchestratorService._run_task_pipeline.  Each step spawns an
agent via an injectable ``spawn_fn``, reads the verdict, and routes to the
next pipeline step.  No LLM in the control loop.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from codehive.core.git_service import GitError, GitService
from codehive.core.issues import create_issue_log_entry
from codehive.core.orchestrator_service import (
    STEP_ROLE_MAP,
    Verdict,
    build_instructions,
    parse_verdict,
    route_result,
)
from codehive.core.task_queue import pipeline_transition
from codehive.core.verdicts import get_verdict as get_structured_verdict
from codehive.db.models import Issue, Project, Task
from codehive.db.models import Session as SessionModel

logger = logging.getLogger(__name__)

# Type alias for the spawn callable
SpawnFn = Callable[..., Awaitable[str]]


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Result returned by ``TaskExecutionRunner.run()``."""

    final_status: str  # "done" | "flagged" | "cancelled" | "error"
    steps_executed: int = 0
    rejection_count: int = 0
    commit_sha: str | None = None
    last_verdict: str | None = None


# ---------------------------------------------------------------------------
# Steps from current status
# ---------------------------------------------------------------------------

# Maps a task's current pipeline_status to the step that should execute next.
_STEPS_FROM: dict[str, str] = {
    "backlog": "grooming",
    "grooming": "grooming",
    "groomed": "implementing",
    "implementing": "implementing",
    "testing": "testing",
    "accepting": "accepting",
}


# ---------------------------------------------------------------------------
# TaskExecutionRunner
# ---------------------------------------------------------------------------


class TaskExecutionRunner:
    """Drives a single task through the full pipeline deterministically.

    Parameters
    ----------
    db_session_factory:
        Async context-manager factory for DB sessions.
    task_id:
        UUID of the task to execute.
    config:
        Configuration dict.  Supports ``max_rejections_per_step`` (default 3).
    spawn_fn:
        ``async (task_id, step, role, mode, instructions) -> str`` callable
        that spawns an agent and returns its output text.
    """

    def __init__(
        self,
        db_session_factory: Callable[..., Any],
        task_id: uuid.UUID,
        config: dict[str, Any] | None = None,
        spawn_fn: SpawnFn | None = None,
    ) -> None:
        self.db_session_factory = db_session_factory
        self.task_id = task_id
        self.config: dict[str, Any] = config or {}
        self.config.setdefault("max_rejections_per_step", 3)
        self._spawn_fn = spawn_fn

        # Internal state
        self._cancelled = False
        self._current_step: str | None = None
        self._steps_executed: int = 0
        self._rejection_count: int = 0
        self._last_verdict: str | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> RunResult:
        """Drive the task through the pipeline to completion (or flagged/cancelled/error)."""
        self._running = True
        try:
            return await self._run_inner()
        finally:
            self._running = False

    def cancel(self) -> None:
        """Request cancellation.  Runner stops after the current step finishes."""
        self._cancelled = True

    def get_status(self) -> dict[str, Any]:
        """Return snapshot of runner state."""
        return {
            "task_id": str(self.task_id),
            "current_step": self._current_step,
            "steps_executed": self._steps_executed,
            "rejection_count": self._rejection_count,
            "last_verdict": self._last_verdict,
            "running": self._running,
            "cancelled": self._cancelled,
        }

    # ------------------------------------------------------------------
    # Internal pipeline loop
    # ------------------------------------------------------------------

    async def _run_inner(self) -> RunResult:
        # Load the task to find its current status
        async with self.db_session_factory() as db:
            task = await db.get(Task, self.task_id)

        if task is None:
            return RunResult(final_status="error", last_verdict=None)

        current_status = task.pipeline_status

        # Already done -- nothing to do
        if current_status == "done":
            return RunResult(final_status="done", steps_executed=0)

        last_output: str = ""
        last_feedback: str = ""

        while True:
            # Check cancellation
            if self._cancelled:
                return RunResult(
                    final_status="cancelled",
                    steps_executed=self._steps_executed,
                    rejection_count=self._rejection_count,
                    last_verdict=self._last_verdict,
                )

            # Determine next step
            next_step = _STEPS_FROM.get(current_status)
            if next_step is None:
                # Terminal or unknown status
                break

            # Transition to the active step if needed (from backlog or groomed)
            if current_status in ("backlog", "groomed"):
                async with self.db_session_factory() as db:
                    await pipeline_transition(db, self.task_id, next_step, actor="task_runner")
                current_status = next_step

            self._current_step = current_status

            # Run the step (with crash/retry)
            result = await self._run_step_with_retry(current_status, last_feedback, last_output)

            self._steps_executed += 1
            self._last_verdict = result.verdict.value
            last_output = result.output

            # Route the result
            target = route_result(current_status, result.verdict)
            if target is None:
                return RunResult(
                    final_status="error",
                    steps_executed=self._steps_executed,
                    rejection_count=self._rejection_count,
                    last_verdict=self._last_verdict,
                )

            # Handle rejections
            if target == "implementing" and current_status in ("testing", "accepting"):
                self._rejection_count += 1
                last_feedback = result.feedback or result.output

                if self._rejection_count >= self.config["max_rejections_per_step"]:
                    # Flag the task
                    await self._log_flagged()
                    return RunResult(
                        final_status="flagged",
                        steps_executed=self._steps_executed,
                        rejection_count=self._rejection_count,
                        last_verdict=self._last_verdict,
                    )
            else:
                # Clear feedback on forward progress
                if target not in ("implementing",):
                    last_feedback = ""

            # Transition to target
            async with self.db_session_factory() as db:
                await pipeline_transition(db, self.task_id, target, actor="task_runner")

            # Git commit when reaching done
            commit_sha: str | None = None
            if target == "done":
                commit_sha = await self._try_git_commit()
                return RunResult(
                    final_status="done",
                    steps_executed=self._steps_executed,
                    rejection_count=self._rejection_count,
                    commit_sha=commit_sha,
                    last_verdict=self._last_verdict,
                )

            current_status = target

        return RunResult(
            final_status="done" if current_status == "done" else "error",
            steps_executed=self._steps_executed,
            rejection_count=self._rejection_count,
            last_verdict=self._last_verdict,
        )

    # ------------------------------------------------------------------
    # Step execution with retry on crash
    # ------------------------------------------------------------------

    @dataclass
    class _StepResult:
        verdict: Verdict
        output: str = ""
        feedback: str | None = None

    async def _run_step_with_retry(
        self,
        step: str,
        feedback: str,
        last_output: str,
    ) -> _StepResult:
        """Run a pipeline step.  Retries once on exception, then flags."""
        max_attempts = 2  # 1 retry
        for attempt in range(max_attempts):
            try:
                return await self._run_pipeline_step(step, feedback, last_output)
            except Exception:
                logger.exception(
                    "Crash in step %s for task %s (attempt %d)",
                    step,
                    self.task_id,
                    attempt + 1,
                )
                if attempt < max_attempts - 1:
                    # Retry once
                    continue
                # Second failure -- flag
                await self._log_flagged(reason=f"Agent crashed in step '{step}' after retry")
                return self._StepResult(verdict=Verdict.FAIL, output="Agent crashed")

        # Should not reach here, but satisfy type checker
        return self._StepResult(verdict=Verdict.FAIL, output="Agent crashed")  # pragma: no cover

    # ------------------------------------------------------------------
    # Single step execution
    # ------------------------------------------------------------------

    async def _run_pipeline_step(
        self,
        step: str,
        feedback: str,
        last_output: str,
    ) -> _StepResult:
        """Spawn an agent for a single pipeline step, read verdict, return result."""
        # Load task context
        async with self.db_session_factory() as db:
            task = await db.get(Task, self.task_id)
            if task is None:
                return self._StepResult(verdict=Verdict.FAIL, output="Task not found")

            session = await db.get(SessionModel, task.session_id)
            issue: Issue | None = None
            if session and session.issue_id:
                issue = await db.get(Issue, session.issue_id)

            acceptance_criteria = issue.acceptance_criteria if issue else None
            task_title = task.title
            task_instructions = task.instructions

        instructions = build_instructions(
            step=step,
            task_title=task_title,
            task_instructions=task_instructions,
            acceptance_criteria=acceptance_criteria,
            feedback=feedback if feedback else None,
            agent_output=last_output if last_output else None,
        )

        role_config = STEP_ROLE_MAP.get(step, {"role": "swe", "mode": "execution"})

        # Spawn agent
        if self._spawn_fn is None:
            output = ""
        else:
            output = await self._spawn_fn(
                task_id=self.task_id,
                step=step,
                role=role_config["role"],
                mode=role_config["mode"],
                instructions=instructions,
            )

        # Log agent output
        async with self.db_session_factory() as db:
            task = await db.get(Task, self.task_id)
            if task:
                session = await db.get(SessionModel, task.session_id)
                if session and session.issue_id:
                    await create_issue_log_entry(
                        db,
                        issue_id=session.issue_id,
                        agent_role=role_config["role"],
                        content=output or "(no output)",
                    )

        # Resolve verdict -- structured first, fallback to regex
        structured_verdict = await self._get_structured_verdict(step)

        if structured_verdict is not None:
            verdict_str = structured_verdict.get("verdict", "FAIL")
            try:
                verdict = Verdict(verdict_str)
            except ValueError:
                verdict = Verdict.FAIL
            return self._StepResult(
                verdict=verdict,
                output=output,
                feedback=structured_verdict.get("feedback"),
            )

        # Regex fallback
        verdict = parse_verdict(output)
        return self._StepResult(verdict=verdict, output=output)

    async def _get_structured_verdict(self, step: str) -> dict[str, Any] | None:
        """Try to find a structured verdict from the most recent child session."""
        from sqlalchemy import select

        async with self.db_session_factory() as db:
            child_stmt = (
                select(SessionModel)
                .where(
                    SessionModel.task_id == self.task_id,
                    SessionModel.pipeline_step == step,
                )
                .order_by(SessionModel.created_at.desc())
                .limit(1)
            )
            child_result = await db.execute(child_stmt)
            child_session = child_result.scalar_one_or_none()

            if child_session is None:
                return None

            return await get_structured_verdict(db, child_session.id)

    # ------------------------------------------------------------------
    # Git commit
    # ------------------------------------------------------------------

    async def _try_git_commit(self) -> str | None:
        """Attempt git commit when task reaches done.  Non-fatal on failure."""
        async with self.db_session_factory() as db:
            task = await db.get(Task, self.task_id)
            if task is None:
                return None
            session = await db.get(SessionModel, task.session_id)
            if session is None:
                return None
            project = await db.get(Project, session.project_id)
            if project is None:
                return None

        try:
            sha = await GitService.commit_task(project, task)
            return sha
        except GitError as e:
            logger.warning("Git commit failed for task %s: %s", self.task_id, e)
            return None

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    async def _log_flagged(self, reason: str | None = None) -> None:
        """Create a log entry when a task is flagged for human review."""
        msg = reason or (f"Task flagged for human review after {self._rejection_count} rejections")
        try:
            async with self.db_session_factory() as db:
                task = await db.get(Task, self.task_id)
                if task is None:
                    return
                session = await db.get(SessionModel, task.session_id)
                if session and session.issue_id:
                    await create_issue_log_entry(
                        db,
                        issue_id=session.issue_id,
                        agent_role="task_runner",
                        content=msg,
                    )
        except Exception:
            logger.exception("Failed to log flagged task %s", self.task_id)


# ---------------------------------------------------------------------------
# Runner registry: track running runners for cancel/status
# ---------------------------------------------------------------------------

_runner_registry: dict[uuid.UUID, TaskExecutionRunner] = {}


def get_runner(task_id: uuid.UUID) -> TaskExecutionRunner | None:
    """Get a running runner for a task, if any."""
    return _runner_registry.get(task_id)


def register_runner(runner: TaskExecutionRunner) -> None:
    """Register a runner.  Raises ValueError if one is already running."""
    existing = _runner_registry.get(runner.task_id)
    if existing and existing._running:
        raise ValueError(f"Runner already active for task {runner.task_id}")
    _runner_registry[runner.task_id] = runner


def unregister_runner(task_id: uuid.UUID) -> None:
    """Remove a runner from the registry."""
    _runner_registry.pop(task_id, None)


def clear_runner_registry() -> None:
    """Clear the runner registry (for tests)."""
    _runner_registry.clear()
