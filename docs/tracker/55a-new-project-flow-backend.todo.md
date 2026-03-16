# 55a: New Project Flow -- Backend

## Description
Backend API for guided project creation. Supports four flows: brainstorm, guided interview, spec from notes, and start from repo. Each flow produces a project brief with knowledge, suggested sessions, and open decisions.

## Implementation Plan

### 1. New project flow endpoints
- `backend/codehive/api/routes/project_flow.py`
- `POST /api/project-flow/start` -- start a new project flow
  - Body: `{flow_type: "brainstorm" | "interview" | "spec_from_notes" | "start_from_repo", initial_input: str}`
  - Creates a temporary session in interview/brainstorm mode
  - Returns `{flow_id, session_id, first_questions: [...]}`

- `POST /api/project-flow/{flow_id}/respond` -- user responds to questions
  - Body: `{answers: [{question_id, answer}]}`
  - Agent processes answers, may ask follow-up questions
  - Returns `{next_questions: [...] | null, brief: ProjectBrief | null}`

- `POST /api/project-flow/{flow_id}/finalize` -- user approves the brief
  - Creates the actual project with populated knowledge
  - Creates suggested sessions
  - Returns `{project_id, sessions: [...]}`

### 2. Project brief generation
- `backend/codehive/core/project_flow.py`
- `async def generate_brief(db, flow_id)` -- uses NativeEngine to synthesize answers into:
  - Project name and description
  - Tech stack (for knowledge base)
  - Architecture overview
  - Open decisions (unresolved questions)
  - Suggested first sessions with missions
  - Suggested archetype

### 3. Flow types
- **Brainstorm**: free-form conversation, agent asks open questions, identifies gaps
- **Interview**: structured batched questions (3-7 per batch), covers: goals, tech stack, architecture, constraints, team
- **Spec from notes**: user pastes existing notes/spec, agent extracts structure
- **Start from repo**: user provides git URL, agent clones and analyzes (uses knowledge auto-populate #56 logic)

### 4. Schema
- `backend/codehive/api/schemas/project_flow.py`
- `ProjectFlowStart`, `ProjectFlowResponse`, `ProjectBrief`, `ProjectFlowFinalize`

## Acceptance Criteria

- [ ] `POST /api/project-flow/start` creates a flow and returns first questions
- [ ] `POST /api/project-flow/{flow_id}/respond` processes answers and returns follow-ups or a brief
- [ ] `POST /api/project-flow/{flow_id}/finalize` creates a project with knowledge populated
- [ ] Interview flow asks 3-7 questions per batch
- [ ] Brief includes: name, description, tech stack, architecture, open decisions, suggested sessions
- [ ] Finalize creates the project AND suggested sessions
- [ ] `uv run pytest tests/test_project_flow.py -v` passes with 6+ tests

## Test Scenarios

### Unit: Flow creation
- Start interview flow, verify session is created in interview mode
- Start brainstorm flow, verify session is created in brainstorm mode
- Start spec_from_notes, verify initial input is processed

### Unit: Brief generation
- Mock engine responses, verify brief contains required fields
- Verify knowledge base is populated on finalize

### Integration: Full flow
- Start flow, respond to questions, verify follow-up questions returned
- Finalize flow, verify project is created with correct knowledge
- Verify suggested sessions are created with missions

## Dependencies
- Depends on: #45 (agent modes), #48 (knowledge base), #09 (engine adapter)
