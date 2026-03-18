"""Project flow: guided project creation with stateful flow management."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.schemas.project_flow import (
    FlowQuestion,
    FlowType,
    ProjectBrief,
    SuggestedSession,
)
from codehive.core.archetypes import ArchetypeNotFoundError, apply_archetype_to_knowledge
from codehive.core.knowledge import update_knowledge
from codehive.core.knowledge_analyzer import analyze_codebase
from codehive.core.project import create_project
from codehive.core.session import create_session


class FlowNotFoundError(Exception):
    """Raised when a flow_id does not exist."""


class FlowAlreadyFinalizedError(Exception):
    """Raised when finalize is called on an already-finalized flow."""


# ---------------------------------------------------------------------------
# In-memory flow state store (MVP)
# ---------------------------------------------------------------------------

_FLOW_STATES: dict[uuid.UUID, dict[str, Any]] = {}


def _reset_flow_states() -> None:
    """Clear all flow states. For testing only."""
    _FLOW_STATES.clear()


def get_flow_state(flow_id: uuid.UUID) -> dict[str, Any] | None:
    """Return the flow state for the given ID, or None."""
    return _FLOW_STATES.get(flow_id)


# ---------------------------------------------------------------------------
# Question generation helpers
# ---------------------------------------------------------------------------

_INTERVIEW_QUESTIONS: list[FlowQuestion] = [
    FlowQuestion(id="q1", text="What is the primary goal of this project?", category="goals"),
    FlowQuestion(id="q2", text="Who are the target users or audience?", category="goals"),
    FlowQuestion(
        id="q3",
        text="What programming languages and frameworks do you want to use?",
        category="tech",
    ),
    FlowQuestion(
        id="q4",
        text="Do you have any infrastructure or deployment preferences?",
        category="architecture",
    ),
    FlowQuestion(
        id="q5",
        text="Are there any hard constraints or limitations?",
        category="constraints",
    ),
]

_BRAINSTORM_QUESTIONS: list[FlowQuestion] = [
    FlowQuestion(
        id="b1",
        text="Tell me more about what you're envisioning. What problem does this solve?",
        category="goals",
    ),
]


def _generate_interview_questions() -> list[FlowQuestion]:
    """Return a batch of structured interview questions."""
    return list(_INTERVIEW_QUESTIONS)


def _generate_brainstorm_questions() -> list[FlowQuestion]:
    """Return open-ended brainstorm questions."""
    return list(_BRAINSTORM_QUESTIONS)


def _generate_spec_questions(initial_input: str) -> list[FlowQuestion]:
    """If spec notes are too sparse, ask clarifying questions. Otherwise return empty."""
    if len(initial_input.strip()) < 50:
        return [
            FlowQuestion(
                id="s1",
                text="Your notes are quite brief. Could you provide more detail about the project scope?",
                category="goals",
            ),
        ]
    return []


def _generate_repo_followup_questions(analysis: dict[str, Any]) -> list[FlowQuestion]:
    """Generate follow-up questions based on gaps in the auto-detected analysis."""
    questions: list[FlowQuestion] = []
    if not analysis.get("tech_stack"):
        questions.append(
            FlowQuestion(
                id="r1",
                text="Could not auto-detect the tech stack. What languages and frameworks does this project use?",
                category="tech",
            )
        )
    questions.append(
        FlowQuestion(
            id="r2",
            text="What is the main goal or purpose of this repository?",
            category="goals",
        )
    )
    return questions


# ---------------------------------------------------------------------------
# Brief generation
# ---------------------------------------------------------------------------


async def generate_brief(flow_state: dict[str, Any]) -> ProjectBrief:
    """Synthesize answers and analysis into a ProjectBrief.

    In production this would call the ZaiEngine. For now we build
    a deterministic brief from the collected answers and analysis data.
    """
    answers = flow_state.get("answers_received", [])
    analysis = flow_state.get("analysis", {})
    initial_input = flow_state.get("initial_input", "")

    # Extract info from answers
    name_parts: list[str] = []
    description_parts: list[str] = []
    for ans in answers:
        description_parts.append(ans.get("answer", ""))
        if ans.get("question_id") in ("q1", "b1", "s1", "r2"):
            name_parts.append(ans["answer"])

    project_name = name_parts[0][:60] if name_parts else "New Project"
    description = (
        " ".join(description_parts) if description_parts else initial_input or "A new project"
    )

    # Tech stack from analysis or answers
    tech_stack = analysis.get("tech_stack", {})
    if not tech_stack:
        for ans in answers:
            if ans.get("question_id") in ("q3", "r1"):
                tech_stack = {"description": ans["answer"]}
                break

    architecture = analysis.get("architecture", {})
    for ans in answers:
        if ans.get("question_id") == "q4":
            architecture["deployment"] = ans["answer"]

    open_decisions: list[dict[str, Any]] = []
    for ans in answers:
        if ans.get("question_id") == "q5" and ans.get("answer"):
            open_decisions.append({"question": ans["answer"]})

    suggested_sessions = [
        SuggestedSession(
            name="Initial Planning",
            mission="Create project structure and initial milestones",
            mode="planning",
        ),
        SuggestedSession(
            name="Implementation",
            mission="Implement core features",
            mode="execution",
        ),
    ]

    return ProjectBrief(
        name=project_name,
        description=description,
        tech_stack=tech_stack,
        architecture=architecture,
        open_decisions=open_decisions,
        suggested_sessions=suggested_sessions,
        suggested_archetype=None,
    )


# ---------------------------------------------------------------------------
# Flow lifecycle
# ---------------------------------------------------------------------------


async def start_flow(
    db: AsyncSession,
    flow_type: FlowType,
    initial_input: str = "",
) -> tuple[uuid.UUID, uuid.UUID, list[FlowQuestion]]:
    """Start a new project flow.

    Returns (flow_id, session_id, first_questions).
    """
    flow_id = uuid.uuid4()

    # Determine mode for the temporary session
    if flow_type in (FlowType.brainstorm, FlowType.spec_from_notes):
        mode = "brainstorm"
    else:
        mode = "interview"

    # We need a project to attach the session to. Create a temporary one.
    project = await create_project(
        db,
        name=f"_flow_{flow_id}",
        description="Temporary project for flow",
    )

    session = await create_session(
        db,
        project_id=project.id,
        name=f"project-flow-{flow_type.value}",
        engine="native",
        mode=mode,
    )

    # Generate initial questions based on flow type
    analysis: dict[str, Any] = {}
    if flow_type == FlowType.interview:
        questions = _generate_interview_questions()
    elif flow_type == FlowType.brainstorm:
        questions = _generate_brainstorm_questions()
    elif flow_type == FlowType.spec_from_notes:
        questions = _generate_spec_questions(initial_input)
    elif flow_type == FlowType.start_from_repo:
        analysis = await analyze_codebase(initial_input)
        questions = _generate_repo_followup_questions(analysis)
    else:
        questions = _generate_interview_questions()

    # Store flow state
    _FLOW_STATES[flow_id] = {
        "flow_id": flow_id,
        "flow_type": flow_type.value,
        "project_id": project.id,
        "session_id": session.id,
        "status": "active",
        "questions_asked": [q.model_dump() for q in questions],
        "answers_received": [],
        "brief": None,
        "initial_input": initial_input,
        "analysis": analysis,
        "round": 1,
    }

    return flow_id, session.id, questions


async def respond_to_flow(
    flow_id: uuid.UUID,
    answers: list[dict[str, str]],
) -> tuple[list[FlowQuestion] | None, ProjectBrief | None]:
    """Process user answers for a flow.

    Returns (next_questions, brief). Exactly one is non-None.
    Raises FlowNotFoundError if flow_id does not exist.
    """
    state = _FLOW_STATES.get(flow_id)
    if state is None:
        raise FlowNotFoundError(f"Flow {flow_id} not found")

    # Record answers
    state["answers_received"].extend(answers)

    flow_type = state["flow_type"]
    current_round = state.get("round", 1)

    # Determine if we need more questions
    if flow_type == "brainstorm" and current_round < 2:
        # Brainstorm gets one follow-up round
        state["round"] = current_round + 1
        follow_up = [
            FlowQuestion(
                id="b2",
                text="What would success look like for this project?",
                category="goals",
            ),
            FlowQuestion(
                id="b3",
                text="Any specific technology preferences?",
                category="tech",
            ),
        ]
        state["questions_asked"].extend([q.model_dump() for q in follow_up])
        return follow_up, None

    # All rounds complete -- generate brief
    brief = await generate_brief(state)
    state["brief"] = brief.model_dump()
    state["status"] = "brief_ready"
    return None, brief


async def finalize_flow(
    db: AsyncSession,
    flow_id: uuid.UUID,
) -> tuple[uuid.UUID, list[dict[str, Any]]]:
    """Finalize a flow: create project, populate knowledge, create sessions.

    Returns (project_id, list of created session dicts).
    Raises FlowNotFoundError or FlowAlreadyFinalizedError.
    """
    state = _FLOW_STATES.get(flow_id)
    if state is None:
        raise FlowNotFoundError(f"Flow {flow_id} not found")

    if state["status"] == "finalized":
        raise FlowAlreadyFinalizedError(f"Flow {flow_id} is already finalized")

    # If brief hasn't been generated yet, generate it now
    if state["brief"] is None:
        brief = await generate_brief(state)
        state["brief"] = brief.model_dump()
    else:
        brief = ProjectBrief(**state["brief"])

    # Create the real project
    project = await create_project(
        db,
        name=brief.name,
        description=brief.description,
    )

    # Populate knowledge
    knowledge_updates: dict[str, Any] = {
        "tech_stack": brief.tech_stack,
        "architecture": brief.architecture,
        "open_decisions": brief.open_decisions,
    }
    await update_knowledge(db, project.id, knowledge_updates)

    # Apply archetype if suggested
    if brief.suggested_archetype:
        try:
            knowledge = apply_archetype_to_knowledge({}, brief.suggested_archetype)
            await update_knowledge(db, project.id, knowledge)
        except ArchetypeNotFoundError:
            pass  # Skip if archetype not found

    # Create sessions for each suggested session
    created_sessions: list[dict[str, Any]] = []
    for suggested in brief.suggested_sessions:
        sess = await create_session(
            db,
            project_id=project.id,
            name=suggested.name,
            engine="native",
            mode=suggested.mode,
        )
        created_sessions.append({"id": sess.id, "name": sess.name, "mode": sess.mode})

    state["status"] = "finalized"

    return project.id, created_sessions
