"""Deterministic pipeline executor -- no LLM in the control loop.

Polls the DB for tasks in actionable pipeline states, spawns the correct
agent session for each step, waits for completion, parses the verdict,
and transitions to the next pipeline step.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.git_service import GitError, GitService
from codehive.core.issues import create_issue_log_entry
from codehive.core.session import create_session as create_db_session
from codehive.core.task_queue import list_tasks, pipeline_transition
from codehive.core.verdicts import get_verdict as get_structured_verdict
from codehive.db.models import AgentProfile, Issue, Project, Task
from codehive.db.models import Session as SessionModel
from codehive.integrations.github.commenter import build_pipeline_message, post_pipeline_comment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "batch_size": 2,
    "poll_interval_seconds": 10,
    "max_rejections_per_step": 3,
    "engine": "claude_code",
    "session_timeout_seconds": 600,
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Verdict(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    NONE = "NONE"


@dataclass
class StepResult:
    verdict: Verdict
    output: str = ""
    session_id: uuid.UUID | None = None
    evidence: list[dict[str, Any]] | None = None
    criteria_results: list[dict[str, Any]] | None = None
    feedback: str | None = None


@dataclass
class OrchestratorState:
    """In-memory state for a running orchestrator."""

    running: bool = False
    project_id: uuid.UUID | None = None
    current_batch: list[uuid.UUID] = field(default_factory=list)
    active_sessions: list[uuid.UUID] = field(default_factory=list)
    rejection_counts: dict[uuid.UUID, int] = field(default_factory=dict)
    flagged_tasks: set[uuid.UUID] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Pipeline step -> agent role mapping
# ---------------------------------------------------------------------------

STEP_ROLE_MAP: dict[str, dict[str, str]] = {
    "grooming": {"role": "pm", "mode": "planning"},
    "implementing": {"role": "swe", "mode": "execution"},
    "testing": {"role": "qa", "mode": "execution"},
    "accepting": {"role": "pm", "mode": "execution"},
}


# ---------------------------------------------------------------------------
# Verdict parsing
# ---------------------------------------------------------------------------

_VERDICT_PATTERNS = [
    (re.compile(r"VERDICT:\s*PASS", re.IGNORECASE), Verdict.PASS),
    (re.compile(r"VERDICT:\s*FAIL", re.IGNORECASE), Verdict.FAIL),
    (re.compile(r"VERDICT:\s*ACCEPT", re.IGNORECASE), Verdict.ACCEPT),
    (re.compile(r"VERDICT:\s*REJECT", re.IGNORECASE), Verdict.REJECT),
]


def parse_verdict(text: str) -> Verdict:
    """Extract PASS/FAIL/ACCEPT/REJECT from agent output text.

    Falls back to FAIL if ambiguous (safe default).
    """
    if not text:
        return Verdict.FAIL

    for pattern, verdict in _VERDICT_PATTERNS:
        if pattern.search(text):
            return verdict

    # No clear verdict found -- safe default
    return Verdict.FAIL


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def route_result(step: str, verdict: Verdict) -> str | None:
    """Decide the next pipeline_status based on current step + verdict.

    Returns the target status string, or None if the task should be flagged.
    """
    if step == "grooming":
        return "groomed"

    if step == "implementing":
        return "testing"

    if step == "testing":
        if verdict in (Verdict.PASS, Verdict.ACCEPT, Verdict.NONE):
            return "accepting"
        # FAIL -> back to implementing
        return "implementing"

    if step == "accepting":
        if verdict in (Verdict.ACCEPT, Verdict.PASS):
            return "done"
        # REJECT -> back to implementing
        return "implementing"

    return None


# ---------------------------------------------------------------------------
# Instruction builders
# ---------------------------------------------------------------------------


def build_instructions(
    step: str,
    task_title: str,
    task_instructions: str | None,
    acceptance_criteria: str | None = None,
    feedback: str | None = None,
    agent_output: str | None = None,
) -> str:
    """Build the initial message/instructions for an agent session."""
    parts: list[str] = []

    if step == "grooming":
        parts.append(f"## Task to Groom\n\nTitle: {task_title}")
        if task_instructions:
            parts.append(f"Description: {task_instructions}")
        parts.append(
            "\nPlease groom this task: define acceptance criteria, "
            "user stories, and test scenarios."
        )

    elif step == "implementing":
        parts.append(f"## Task to Implement\n\nTitle: {task_title}")
        if acceptance_criteria:
            parts.append(f"Acceptance Criteria:\n{acceptance_criteria}")
        if task_instructions:
            parts.append(f"Description: {task_instructions}")
        if feedback:
            parts.append(f"\n## Feedback from Previous Review\n\n{feedback}")
        parts.append("\nImplement this task. Write code and tests.")

    elif step == "testing":
        parts.append(f"## Task to Test\n\nTitle: {task_title}")
        if acceptance_criteria:
            parts.append(f"Acceptance Criteria:\n{acceptance_criteria}")
        if agent_output:
            parts.append(f"\n## SWE Output\n\n{agent_output}")
        parts.append(
            "\nVerify the implementation. Run tests and check acceptance criteria. "
            "End with VERDICT: PASS or VERDICT: FAIL.\n\n"
            "Preferred: call submit_verdict with a structured payload:\n"
            '  submit_verdict(session_id, verdict="PASS"|"FAIL", role="qa", '
            "task_id=<uuid>,\n"
            '    evidence=[{"type": "test_output", "content": "..."}],\n'
            '    criteria_results=[{"criterion": "...", "result": "PASS"|"FAIL"}],\n'
            '    feedback="optional feedback")'
        )

    elif step == "accepting":
        parts.append(f"## Task to Accept\n\nTitle: {task_title}")
        if acceptance_criteria:
            parts.append(f"Acceptance Criteria:\n{acceptance_criteria}")
        if agent_output:
            parts.append(f"\n## QA Evidence\n\n{agent_output}")
        parts.append(
            "\nReview the QA evidence and decide. End with VERDICT: ACCEPT or VERDICT: REJECT.\n\n"
            "Preferred: call submit_verdict with a structured payload:\n"
            '  submit_verdict(session_id, verdict="ACCEPT"|"REJECT", role="pm", '
            "task_id=<uuid>,\n"
            '    evidence=[{"type": "...", "content": "..."}],\n'
            '    feedback="optional rejection reason")'
        )

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# OrchestratorService
# ---------------------------------------------------------------------------


class OrchestratorService:
    """Deterministic pipeline executor. No LLM in the control loop."""

    def __init__(
        self,
        db_session_factory: Callable[..., Any],
        project_id: uuid.UUID,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.state = OrchestratorState(project_id=project_id)
        self._db_session_factory = db_session_factory
        self._task: asyncio.Task[None] | None = None

        # Hook for spawning agent sessions -- can be replaced in tests.
        self._spawn_and_run: Callable[..., Any] | None = None

    @property
    def running(self) -> bool:
        return self.state.running

    async def start(self) -> None:
        """Start the main loop as a background asyncio task."""
        if self.state.running:
            return
        self.state.running = True
        self._task = asyncio.create_task(self._main_loop())

    async def stop(self) -> None:
        """Signal the loop to stop after current batch finishes."""
        self.state.running = False
        if self._task and not self._task.done():
            # Let it finish gracefully -- don't cancel
            pass

    async def _main_loop(self) -> None:
        """Poll -> pick batch -> execute pipeline steps -> repeat."""
        while self.state.running:
            try:
                async with self._db_session_factory() as db:
                    batch = await self._pick_batch(db)

                if not batch:
                    await asyncio.sleep(self.config["poll_interval_seconds"])
                    continue

                self.state.current_batch = [t.id for t in batch]

                # Run all tasks in the batch in parallel
                await asyncio.gather(
                    *(self._run_task_pipeline(task) for task in batch),
                    return_exceptions=True,
                )

                self.state.current_batch = []

            except Exception:
                logger.exception("Orchestrator loop error")
                if self.state.running:
                    await asyncio.sleep(self.config["poll_interval_seconds"])

    async def _pick_batch(self, db: AsyncSession) -> list[Task]:
        """Pick up to batch_size tasks with pipeline_status='backlog'."""
        # Find the orchestrator session for this project
        session_id = await self._get_or_create_session_id(db)
        tasks = await list_tasks(db, session_id, pipeline_status="backlog")
        return tasks[: self.config["batch_size"]]

    async def _get_or_create_session_id(self, db: AsyncSession) -> uuid.UUID:
        """Get the orchestrator session ID, creating one if needed."""
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.project_id == self.project_id,
                SessionModel.name == f"orchestrator-{self.project_id}",
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session.id

        session = await create_db_session(
            db,
            project_id=self.project_id,
            name=f"orchestrator-{self.project_id}",
            engine=self.config["engine"],
            mode="orchestrator",
        )
        return session.id

    async def _run_task_pipeline(self, task: Task) -> None:
        """Run the full pipeline for a single task.

        Continues until the task reaches "done", is flagged, or the service
        is stopped (checked between steps to allow graceful shutdown).
        """
        task_id = task.id
        current_step = task.pipeline_status

        # Pipeline order: backlog -> grooming -> groomed -> implementing -> testing -> accepting -> done
        steps_from: dict[str, str] = {
            "backlog": "grooming",
            "grooming": "grooming",
            "groomed": "implementing",
            "implementing": "implementing",
            "testing": "testing",
            "accepting": "accepting",
        }

        last_output: str = ""
        last_feedback: str = ""

        while True:
            if task_id in self.state.flagged_tasks:
                break

            # Get the next step to execute
            next_step = steps_from.get(current_step)
            if next_step is None or current_step == "done":
                break

            # Transition to the active step if needed
            if current_step in ("backlog", "groomed"):
                async with self._db_session_factory() as db:
                    await pipeline_transition(db, task_id, next_step, actor="orchestrator")
                current_step = next_step
                # Post GitHub comment for the step transition
                await self._try_post_github_comment(task_id, current_step)

            # Run the step
            result = await self._run_pipeline_step(
                task_id, current_step, last_feedback, last_output
            )

            last_output = result.output

            # Route the result
            target = route_result(current_step, result.verdict)
            if target is None:
                break

            # Check rejection limits
            if target == "implementing" and current_step in ("testing", "accepting"):
                count = self.state.rejection_counts.get(task_id, 0) + 1
                self.state.rejection_counts[task_id] = count
                # Prefer structured feedback over raw output
                last_feedback = result.feedback or result.output

                if count >= self.config["max_rejections_per_step"]:
                    self.state.flagged_tasks.add(task_id)
                    # Log the flagging
                    async with self._db_session_factory() as db:
                        # Find issue_id from task's session
                        refreshed_task = await db.get(Task, task_id)
                        if refreshed_task:
                            session = await db.get(SessionModel, refreshed_task.session_id)
                            if session and session.issue_id:
                                await create_issue_log_entry(
                                    db,
                                    issue_id=session.issue_id,
                                    agent_role="orchestrator",
                                    content=f"Task flagged for human review after "
                                    f"{count} rejections.",
                                )
                    break

                # Log the rejection feedback
                async with self._db_session_factory() as db:
                    refreshed_task = await db.get(Task, task_id)
                    if refreshed_task:
                        session = await db.get(SessionModel, refreshed_task.session_id)
                        if session and session.issue_id:
                            role = "qa" if current_step == "testing" else "pm"
                            await create_issue_log_entry(
                                db,
                                issue_id=session.issue_id,
                                agent_role=role,
                                content=result.output or "Rejected",
                            )

            # Transition
            async with self._db_session_factory() as db:
                await pipeline_transition(db, task_id, target, actor="orchestrator")

            # Git commit after transitioning to done
            commit_sha: str | None = None
            if target == "done":
                commit_sha = await self._try_git_commit(task_id)

            # Post GitHub comment for the transition
            await self._try_post_github_comment(task_id, target, commit_sha=commit_sha)

            current_step = target

    async def _try_post_github_comment(
        self, task_id: uuid.UUID, step: str, commit_sha: str | None = None
    ) -> None:
        """Post a pipeline progress comment on the linked GitHub issue, if any.

        Non-fatal: errors are logged and swallowed so the pipeline continues.
        """
        try:
            async with self._db_session_factory() as db:
                task = await db.get(Task, task_id)
                if task is None:
                    return
                session = await db.get(SessionModel, task.session_id)
                if session is None or session.issue_id is None:
                    return
                issue = await db.get(Issue, session.issue_id)
                if issue is None or issue.github_issue_id is None:
                    return
                project = await db.get(Project, issue.project_id)
                if project is None:
                    return
                config = project.github_config or {}
                owner = config.get("owner")
                repo = config.get("repo")
                token = config.get("token")
                if not (owner and repo and token):
                    return
                gh_issue_number = issue.github_issue_id

            message = build_pipeline_message(step, commit_sha=commit_sha)
            await post_pipeline_comment(owner, repo, gh_issue_number, token, message)
        except Exception:
            logger.warning(
                "Failed to post GitHub comment for task %s step %s",
                task_id,
                step,
                exc_info=True,
            )

    async def _try_git_commit(self, task_id: uuid.UUID) -> str | None:
        """Attempt to git-commit after a task reaches done. Non-fatal on failure.

        Returns the commit SHA on success, or None on failure/skip.
        """
        async with self._db_session_factory() as db:
            task = await db.get(Task, task_id)
            if task is None:
                return None
            session = await db.get(SessionModel, task.session_id)
            if session is None:
                return None
            project = await db.get(Project, session.project_id)
            issue_id = session.issue_id

        try:
            sha = await GitService.commit_task(project, task)
            if sha and issue_id:
                async with self._db_session_factory() as db:
                    await create_issue_log_entry(
                        db,
                        issue_id=issue_id,
                        agent_role="orchestrator",
                        content=f"Git commit: {sha}",
                    )
            return sha
        except GitError as e:
            logger.warning("Git commit failed for task %s: %s", task_id, e)
            if issue_id:
                async with self._db_session_factory() as db:
                    await create_issue_log_entry(
                        db,
                        issue_id=issue_id,
                        agent_role="orchestrator",
                        content=f"Git commit failed: {e}",
                    )
            return None

    async def _resolve_agent_profile(
        self,
        db: AsyncSession,
        role: str,
    ) -> AgentProfile | None:
        """Find an agent profile for the given role from the project's team.

        Uses round-robin selection based on the number of existing sessions
        with that role. Returns None if no profile matches (graceful fallback).
        """
        result = await db.execute(
            select(AgentProfile).where(
                AgentProfile.project_id == self.project_id,
                AgentProfile.role == role,
            )
        )
        profiles = list(result.scalars().all())
        if not profiles:
            return None
        # Simple round-robin: count sessions with this role to pick next
        session_count_result = await db.execute(
            select(SessionModel).where(
                SessionModel.project_id == self.project_id,
                SessionModel.role == role,
            )
        )
        session_count = len(list(session_count_result.scalars().all()))
        return profiles[session_count % len(profiles)]

    async def _run_pipeline_step(
        self,
        task_id: uuid.UUID,
        step: str,
        feedback: str = "",
        last_output: str = "",
    ) -> StepResult:
        """Spawn an agent session for the given step, wait for result."""
        async with self._db_session_factory() as db:
            task = await db.get(Task, task_id)
            if task is None:
                return StepResult(verdict=Verdict.FAIL, output="Task not found")

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

        # Spawn the agent session
        role_config = STEP_ROLE_MAP.get(step, {"role": "swe", "mode": "execution"})

        # Resolve agent profile for this role
        agent_profile_id: uuid.UUID | None = None
        async with self._db_session_factory() as db:
            agent_profile = await self._resolve_agent_profile(db, role_config["role"])
            if agent_profile is not None:
                agent_profile_id = agent_profile.id

        if self._spawn_and_run:
            output = await self._spawn_and_run(
                task_id=task_id,
                step=step,
                role=role_config["role"],
                mode=role_config["mode"],
                instructions=instructions,
            )
        else:
            output = await self._default_spawn_and_run(
                task_id=task_id,
                step=step,
                role=role_config["role"],
                mode=role_config["mode"],
                instructions=instructions,
                agent_profile_id=agent_profile_id,
            )

        # Log the agent output
        child_session_id: uuid.UUID | None = None
        async with self._db_session_factory() as db:
            task = await db.get(Task, task_id)
            if task:
                session = await db.get(SessionModel, task.session_id)
                if session and session.issue_id:
                    await create_issue_log_entry(
                        db,
                        issue_id=session.issue_id,
                        agent_role=role_config["role"],
                        content=output or "(no output)",
                        agent_profile_id=agent_profile_id,
                    )

            # Find the most recent child session for this task+step
            child_stmt = (
                select(SessionModel)
                .where(
                    SessionModel.task_id == task_id,
                    SessionModel.pipeline_step == step,
                )
                .order_by(SessionModel.created_at.desc())
                .limit(1)
            )
            child_result = await db.execute(child_stmt)
            child_session = child_result.scalar_one_or_none()
            if child_session:
                child_session_id = child_session.id

        # Try structured verdict first, fall back to regex parsing
        structured_verdict: dict[str, Any] | None = None
        if child_session_id is not None:
            async with self._db_session_factory() as db:
                structured_verdict = await get_structured_verdict(db, child_session_id)

        if structured_verdict is not None:
            verdict_str = structured_verdict.get("verdict", "FAIL")
            try:
                verdict = Verdict(verdict_str)
            except ValueError:
                verdict = Verdict.FAIL
            return StepResult(
                verdict=verdict,
                output=output,
                session_id=child_session_id,
                evidence=structured_verdict.get("evidence"),
                criteria_results=structured_verdict.get("criteria_results"),
                feedback=structured_verdict.get("feedback"),
            )

        # Fallback: regex-based verdict parsing
        verdict = parse_verdict(output)
        return StepResult(verdict=verdict, output=output)

    def _resolve_sub_agent_engine(self) -> str:
        """Pick an engine for a sub-agent session.

        If ``sub_agent_engines`` is set in the orchestrator config, use the
        first entry.  Otherwise fall back to the orchestrator's own engine.
        """
        engines: list[str] = self.config.get("sub_agent_engines", [])
        if engines:
            return engines[0]
        return self.config["engine"]

    async def _default_spawn_and_run(
        self,
        task_id: uuid.UUID,
        step: str,
        role: str,
        mode: str,
        instructions: str,
        agent_profile_id: uuid.UUID | None = None,
    ) -> str:
        """Default implementation: create a child session and send the message.

        In production this would use _build_engine and send_message.
        For now returns empty string -- tests override via _spawn_and_run hook.
        """
        sub_engine = self._resolve_sub_agent_engine()

        async with self._db_session_factory() as db:
            child_session = await create_db_session(
                db,
                project_id=self.project_id,
                name=f"{role}-{step}-{task_id}",
                engine=sub_engine,
                mode=mode,
                task_id=task_id,
                pipeline_step=step,
            )
            # Set agent_profile_id on the session directly
            if agent_profile_id is not None:
                child_session.agent_profile_id = agent_profile_id
                await db.commit()
                await db.refresh(child_session)
            self.state.active_sessions.append(child_session.id)

        # In a real implementation, we'd build the engine and send the message.
        # This is deferred to engine integration.
        return ""

    def get_status(self) -> dict[str, Any]:
        """Return current orchestrator state as a dict."""
        return {
            "status": "running" if self.state.running else "stopped",
            "project_id": str(self.project_id) if self.project_id else None,
            "current_batch": [str(t) for t in self.state.current_batch],
            "active_sessions": [str(s) for s in self.state.active_sessions],
            "flagged_tasks": [str(t) for t in self.state.flagged_tasks],
        }


# ---------------------------------------------------------------------------
# Registry: ensure one orchestrator per project
# ---------------------------------------------------------------------------

_registry: dict[uuid.UUID, OrchestratorService] = {}


def get_orchestrator(project_id: uuid.UUID) -> OrchestratorService | None:
    """Get the running orchestrator for a project, if any."""
    return _registry.get(project_id)


def register_orchestrator(service: OrchestratorService) -> None:
    """Register an orchestrator. Raises ValueError if one is already running."""
    pid = service.project_id
    existing = _registry.get(pid)
    if existing and existing.running:
        raise ValueError(f"Orchestrator already running for project {pid}")
    _registry[pid] = service


def unregister_orchestrator(project_id: uuid.UUID) -> None:
    """Remove an orchestrator from the registry."""
    _registry.pop(project_id, None)


def clear_registry() -> None:
    """Clear the orchestrator registry (for tests)."""
    _registry.clear()
