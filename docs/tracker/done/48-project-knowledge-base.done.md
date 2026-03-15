# 48: Project Knowledge Base and Agent Charter

## Description
Implement the project knowledge base -- a structured store for tech stack info, architecture decisions, coding conventions, and the agent charter (goals, constraints, decision policies). The agent consults this when making autonomous decisions.

The Project model already has a `knowledge` JSONB field (from #03), and it is already used by the archetype system (#26) to store `archetype_roles` and `archetype_settings`. This issue adds dedicated API endpoints for reading and writing structured knowledge sections and the agent charter, plus core logic for knowledge management, and extends the native engine to inject relevant knowledge into the agent's system prompt.

## Scope

### Core logic: `backend/codehive/core/knowledge.py`
- Define the knowledge base schema with typed sections: `tech_stack`, `architecture`, `conventions`, `decisions`, `open_decisions`
- CRUD operations for knowledge entries that read/write within the project's `knowledge` JSONB field
- Merge semantics: PATCH updates merge into existing knowledge (not replace the whole blob)
- Agent charter as a dedicated sub-document within knowledge (`charter` key): goals, constraints, tech_stack_rules, coding_rules, decision_policies
- Validation: Pydantic models for each knowledge section and the charter
- Must not clobber existing archetype data (`archetype_roles`, `archetype_settings`) when updating knowledge

### API routes: `backend/codehive/api/routes/knowledge.py`
- `GET /api/projects/{project_id}/knowledge` -- Return all knowledge sections for a project
- `PATCH /api/projects/{project_id}/knowledge` -- Merge-update knowledge sections (partial update)
- `GET /api/projects/{project_id}/charter` -- Return the agent charter document
- `PUT /api/projects/{project_id}/charter` -- Replace the agent charter document

### Engine integration: `backend/codehive/engine/native.py`
- Extend the native engine's `send_message` to build a knowledge context block from the project's knowledge and charter
- Inject this block into the system prompt alongside mode/role prompts
- The knowledge context should include: tech stack, conventions, active decisions, and the full charter

### API schemas: `backend/codehive/api/schemas/knowledge.py`
- Pydantic request/response models for knowledge and charter endpoints

### Tests: `backend/tests/test_knowledge.py`
- Unit tests for core knowledge CRUD logic
- Integration tests for all four API endpoints
- Tests for merge semantics (PATCH does not destroy existing keys)
- Tests for archetype data preservation
- Tests for engine context injection

## Endpoints

### `GET /api/projects/{project_id}/knowledge`
- Returns 200 with the full knowledge dict (all sections)
- Returns 404 if project does not exist

### `PATCH /api/projects/{project_id}/knowledge`
- Request body: partial knowledge dict (only sections to update)
- Merge-updates into existing knowledge JSONB, preserving keys not present in request
- Returns 200 with the updated full knowledge dict
- Returns 404 if project does not exist
- Returns 422 for invalid knowledge structure

### `GET /api/projects/{project_id}/charter`
- Returns 200 with the charter sub-document (or empty object if not set)
- Returns 404 if project does not exist

### `PUT /api/projects/{project_id}/charter`
- Request body: full charter document
- Replaces the `charter` key within the knowledge JSONB
- Returns 200 with the saved charter
- Returns 404 if project does not exist
- Returns 422 for invalid charter structure

## Dependencies
- Depends on: #03 (Project model with knowledge JSONB field) -- DONE
- Depends on: #04 (project CRUD API) -- DONE
- Depends on: #09 (engine adapter interface) -- DONE
- Depends on: #45 (agent modes backend, for system prompt patterns) -- DONE

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_knowledge.py -v` passes with 12+ tests
- [ ] `GET /api/projects/{project_id}/knowledge` returns 200 with all knowledge sections for an existing project
- [ ] `GET /api/projects/{project_id}/knowledge` returns 404 for a non-existent project
- [ ] `PATCH /api/projects/{project_id}/knowledge` merges new sections into existing knowledge without destroying unrelated keys
- [ ] `PATCH /api/projects/{project_id}/knowledge` preserves archetype data (`archetype_roles`, `archetype_settings`) when updating other sections
- [ ] `GET /api/projects/{project_id}/charter` returns the charter document (or `{}` if none set)
- [ ] `PUT /api/projects/{project_id}/charter` replaces the charter and the change persists on subsequent GET
- [ ] Charter and knowledge schemas are validated (422 on malformed input)
- [ ] Native engine injects project knowledge and charter into the system prompt when sending messages
- [ ] Knowledge route is registered on the FastAPI app (visible in `/docs`)
- [ ] All existing tests continue to pass: `uv run pytest backend/tests/ -v`

## Test Scenarios

### Unit: Knowledge CRUD (`core/knowledge.py`)
- Get knowledge for a project with empty knowledge -- returns `{}`
- Get knowledge for a project with archetype data -- returns full dict including archetype keys
- Update knowledge with `tech_stack` section -- persists correctly
- Update knowledge twice with different sections -- both sections present
- Update knowledge with a section that already exists -- merges/overwrites that section only
- Verify archetype keys (`archetype_roles`, `archetype_settings`) survive a knowledge update
- Get charter when none is set -- returns `{}`
- Set charter, then get charter -- returns saved charter
- Replace charter -- old charter is fully replaced, not merged

### Integration: Knowledge API endpoints
- `GET /api/projects/{id}/knowledge` on a fresh project returns `{}`
- `PATCH /api/projects/{id}/knowledge` with `{"tech_stack": {"language": "python"}}` returns 200 with that data
- `PATCH` a second time with `{"conventions": {"style": "black"}}` -- response contains both `tech_stack` and `conventions`
- `PATCH` with invalid structure returns 422
- `GET /api/projects/{id}/charter` on a fresh project returns `{}`
- `PUT /api/projects/{id}/charter` with a valid charter returns 200
- `GET /api/projects/{id}/charter` after PUT returns the saved charter
- All endpoints return 404 for non-existent project ID
- `PUT /api/projects/{id}/charter` with invalid body returns 422

### Unit: Engine context injection
- Native engine builds system prompt that includes knowledge context when project has knowledge data
- Native engine system prompt includes charter content when project has a charter
- Native engine system prompt does not include knowledge block when project knowledge is empty

## Knowledge Schema Reference

The knowledge JSONB field should support (but not be limited to) these sections:

```json
{
  "tech_stack": {"language": "python", "framework": "fastapi", "database": "postgresql"},
  "architecture": {"pattern": "hexagonal", "notes": "..."},
  "conventions": {"style": "black", "imports": "isort", "max_line_length": 100},
  "decisions": [
    {"id": "D001", "title": "Use JSONB for knowledge", "status": "accepted", "rationale": "..."}
  ],
  "open_decisions": [
    {"id": "OD001", "question": "Which cache layer?", "options": ["redis", "memcached"], "context": "..."}
  ],
  "charter": {
    "goals": ["Ship MVP by Q2"],
    "constraints": ["No external API calls in tests"],
    "tech_stack_rules": ["Python 3.12+", "Always use async"],
    "coding_rules": ["Type hints required", "Docstrings on public functions"],
    "decision_policies": ["Prefer simplicity over abstraction", "Ask before adding new dependencies"]
  },
  "archetype_roles": ["..."],
  "archetype_settings": {"...": "..."}
}
```

The schema should be flexible (extra keys allowed) since knowledge will evolve over time.

## Log

### [SWE] 2026-03-15 12:00
- Implemented project knowledge base with structured sections and agent charter
- Created core knowledge module with CRUD operations and merge semantics
- Created Pydantic schemas for knowledge and charter with extra fields allowed
- Created API routes: GET/PATCH knowledge, GET/PUT charter
- Extended NativeEngine to inject knowledge context into system prompt
- Knowledge context includes tech_stack, architecture, conventions, decisions, open_decisions, and charter
- Archetype keys (archetype_roles, archetype_settings) are preserved during updates and excluded from system prompt
- Files created: backend/codehive/core/knowledge.py, backend/codehive/api/schemas/knowledge.py, backend/codehive/api/routes/knowledge.py, backend/tests/test_knowledge.py
- Files modified: backend/codehive/api/app.py (router registration), backend/codehive/engine/native.py (knowledge injection)
- Tests added: 31 tests (9 unit core CRUD, 10 API integration, 6 build_knowledge_context, 3 engine injection, 3 charter core)
- Build results: 768 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 13:00
- Tests: 31 passed in test_knowledge.py, 768 passed total (0 failed)
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. `uv run pytest backend/tests/test_knowledge.py -v` passes with 12+ tests: PASS (31 tests)
  2. GET knowledge returns 200 with all sections for existing project: PASS (test_get_knowledge_fresh_project, test_get_knowledge_with_archetype_data)
  3. GET knowledge returns 404 for non-existent project: PASS (test_knowledge_404_nonexistent_project, test_get_knowledge_nonexistent_project)
  4. PATCH knowledge merges without destroying unrelated keys: PASS (test_patch_knowledge_merge, test_update_twice_different_sections)
  5. PATCH knowledge preserves archetype data: PASS (test_archetype_keys_survive_update)
  6. GET charter returns charter or {} if none: PASS (test_get_charter_when_none, test_get_charter_fresh_project)
  7. PUT charter replaces and persists on GET: PASS (test_get_charter_after_put, test_replace_charter)
  8. Charter and knowledge schemas validated (422 on malformed): PASS (test_patch_knowledge_invalid_structure, test_put_charter_invalid_body)
  9. Native engine injects knowledge and charter into system prompt: PASS (test_engine_includes_knowledge_in_system_prompt, test_engine_includes_charter_in_system_prompt, test_engine_no_knowledge_block_when_empty)
  10. Knowledge route registered on FastAPI app: PASS (verified 4 routes in /docs)
  11. All existing tests continue to pass: PASS (768 passed, 2 warnings -- both pre-existing)
- VERDICT: PASS

### [PM] 2026-03-15 14:30
- Reviewed diff: 4 files created (core/knowledge.py, api/routes/knowledge.py, api/schemas/knowledge.py, tests/test_knowledge.py), 2 files modified (api/app.py, engine/native.py)
- Results verified: real data present -- 31 tests exercise all 4 endpoints, merge semantics, archetype preservation, engine injection with mock Anthropic client
- Acceptance criteria: all 11 met
  1. 31 tests pass (requirement: 12+)
  2. GET knowledge returns 200 with all sections
  3. GET knowledge returns 404 for non-existent project
  4. PATCH merges without destroying unrelated keys
  5. PATCH preserves archetype_roles and archetype_settings
  6. GET charter returns {} when none set
  7. PUT charter replaces and persists on GET
  8. 422 validation on malformed tech_stack (expects dict) and goals (expects list)
  9. NativeEngine injects knowledge context into system prompt via build_knowledge_context
  10. Knowledge router registered in create_app
  11. 768 total tests pass
- Follow-up issues created: none
- VERDICT: ACCEPT
