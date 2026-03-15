# 26: Project Archetypes

## Description
Implement project archetypes -- pre-defined templates for common project types. An archetype bundles roles, default settings, workflow definitions, and tech stack info. Archetypes are selectable at project creation time, clonable, and customizable.

## Scope
- `backend/codehive/core/archetypes.py` -- ArchetypeDefinition model, loading from YAML, listing, cloning logic
- `backend/codehive/archetypes/` -- Built-in archetype definitions as YAML (software_development, research, technical_operations, code_maintenance)
- `backend/codehive/api/routes/archetypes.py` -- List/get/clone archetype endpoints
- `backend/codehive/api/schemas/archetype.py` -- Pydantic request/response schemas for archetype endpoints
- `backend/codehive/api/routes/projects.py` -- Extend project creation so that when `archetype` is set, its roles and default settings are auto-applied to the project's `knowledge` JSONB
- `backend/tests/test_archetypes.py` -- Archetype loading, application, and API tests
- Wire the new router into `backend/codehive/api/app.py`

## Dependencies
- Depends on: #25 (agent roles -- done; archetypes reference role names defined there)
- Depends on: #04 (project CRUD API -- done; archetype applied at project creation)

## Archetype YAML Format

Each built-in archetype is a YAML file in `backend/codehive/archetypes/`. Example:

```yaml
name: software_development
display_name: Software Development
description: Full development workflow with PM, developer, and tester roles.
roles:
  - product_manager
  - developer
  - tester
workflow:
  - planning
  - implementation
  - testing
  - review
default_settings:
  auto_start_tasks: true
  require_approval_destructive: true
tech_stack: []
```

## ArchetypeDefinition Model

Pydantic model in `core/archetypes.py` with fields: `name`, `display_name`, `description`, `roles` (list[str]), `workflow` (list[str]), `default_settings` (dict[str, Any]), `tech_stack` (list[str]).

Follow the same pattern as `RoleDefinition` in `core/roles.py`: YAML loading from a sibling `archetypes/` package directory, `set_builtin_dir`/`reset_builtin_dir` for testing, validation via Pydantic.

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_archetypes.py -v` passes with 12+ tests
- [ ] Four built-in archetype YAML files exist: `software_development.yaml`, `research.yaml`, `technical_operations.yaml`, `code_maintenance.yaml`
- [ ] Each archetype YAML has all required fields: name, display_name, description, roles, workflow, default_settings, tech_stack
- [ ] Every role name referenced in an archetype YAML corresponds to an existing built-in role in `backend/codehive/roles/`
- [ ] `list_builtin_archetypes()` returns `["code_maintenance", "research", "software_development", "technical_operations"]` (sorted)
- [ ] `load_archetype("software_development")` returns an ArchetypeDefinition with roles `["product_manager", "developer", "tester"]`
- [ ] `load_archetype("nonexistent")` raises `ArchetypeNotFoundError`
- [ ] GET `/api/archetypes` returns 200 with a JSON list of all four built-in archetypes
- [ ] GET `/api/archetypes/software_development` returns 200 with the full archetype definition
- [ ] GET `/api/archetypes/nonexistent` returns 404
- [ ] POST `/api/projects` with `archetype: "software_development"` creates the project AND auto-populates `knowledge.archetype_roles` with the archetype's role list and `knowledge.archetype_settings` with the archetype's default_settings
- [ ] POST `/api/projects` with `archetype: null` (or omitted) still works as before with no archetype-related knowledge entries
- [ ] POST `/api/projects` with `archetype: "nonexistent"` returns 400 (invalid archetype)
- [ ] Clone endpoint: POST `/api/archetypes/{name}/clone` with body `{"name": "my_custom_archetype", ...overrides}` creates a custom archetype stored in the DB, returns 201
- [ ] Cloned archetypes appear alongside built-in archetypes in GET `/api/archetypes`
- [ ] Cloning with a name that conflicts with a built-in archetype returns 409

## Test Scenarios

### Unit: Archetype loading (test_archetypes.py)
- Load each of the four built-in archetypes by name, verify all fields are populated
- `list_builtin_archetypes()` returns exactly the four expected names, sorted
- Loading a nonexistent archetype raises `ArchetypeNotFoundError`
- Archetype YAML with missing required fields raises `ValidationError`
- All role names in each built-in archetype are valid (exist in `list_builtin_roles()`)

### Unit: Archetype application to project knowledge
- Given an archetype name, `apply_archetype_to_knowledge({}, "software_development")` returns a dict with `archetype_roles` and `archetype_settings` keys populated from the archetype
- Applying archetype to existing knowledge dict preserves other keys
- Applying with `archetype=None` returns knowledge unchanged

### Integration: API endpoints (test_archetypes.py)
- GET `/api/archetypes` returns 200, response is a list with 4+ items, each having name/display_name/description/roles/workflow fields
- GET `/api/archetypes/research` returns 200 with correct research archetype data
- GET `/api/archetypes/nonexistent` returns 404
- POST `/api/projects` with valid archetype populates knowledge correctly (check via GET on the created project)
- POST `/api/projects` with invalid archetype returns 400
- POST `/api/archetypes/software_development/clone` with a new name returns 201 and the cloned archetype
- POST clone with duplicate built-in name returns 409
- GET `/api/archetypes` after cloning includes the custom archetype

## Implementation Notes
- Follow the same structural patterns established in #25 (roles): YAML in a package directory, Pydantic model, core module with load/list functions, API routes with schemas, `set_builtin_dir` for test isolation.
- The `Project.archetype` column already exists (Unicode(100), nullable). The `knowledge` JSONB column is where archetype-derived data gets stored.
- Custom (cloned) archetypes can be stored in a new `custom_archetypes` DB table (same pattern as `CustomRole`), or in the existing `Workspace.settings` JSONB. A dedicated table is preferred for consistency with `custom_roles`.
- Wire the new archetype router into `app.py` the same way the roles router is wired.

## Log

### [SWE] 2026-03-15 12:00
- Implemented project archetypes following the same pattern as agent roles (#25)
- Created ArchetypeDefinition Pydantic model with YAML loading, set_builtin_dir/reset_builtin_dir for testing
- Created four built-in archetype YAML files (software_development, research, technical_operations, code_maintenance)
- All archetype role references validated against existing built-in roles
- Added apply_archetype_to_knowledge() to populate project knowledge JSONB on creation
- Extended project creation (core/project.py) to apply archetype when set, raising InvalidArchetypeError for invalid names
- Extended project creation API (routes/projects.py) to return 400 for invalid archetypes
- Added CustomArchetype DB model for storing cloned archetypes
- Created API routes: GET /api/archetypes, GET /api/archetypes/{name}, POST /api/archetypes/{name}/clone
- Created Pydantic schemas: ArchetypeRead, ArchetypeCloneRequest
- Wired archetypes_router into app.py
- Updated test_models.py to include custom_archetypes table in expected set
- Files created: backend/codehive/archetypes/__init__.py, backend/codehive/archetypes/software_development.yaml, backend/codehive/archetypes/research.yaml, backend/codehive/archetypes/technical_operations.yaml, backend/codehive/archetypes/code_maintenance.yaml, backend/codehive/core/archetypes.py, backend/codehive/api/schemas/archetype.py, backend/codehive/api/routes/archetypes.py, backend/tests/test_archetypes.py
- Files modified: backend/codehive/db/models.py, backend/codehive/core/project.py, backend/codehive/api/routes/projects.py, backend/codehive/api/app.py, backend/tests/test_models.py
- Tests added: 21 tests (8 unit loading, 4 unit application, 9 integration API)
- Build results: 486 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 13:30
- Tests: 21 passed, 0 failed (test_archetypes.py); 486 passed, 0 failed (full suite)
- Ruff: clean (check + format)
- Acceptance criteria:
  1. 12+ tests pass: PASS (21 tests)
  2. Four built-in YAML files exist: PASS
  3. Each YAML has all required fields: PASS
  4. Role names reference existing built-in roles: PASS (verified against roles/)
  5. list_builtin_archetypes() returns sorted list: PASS
  6. load_archetype("software_development") returns correct ArchetypeDefinition: PASS
  7. load_archetype("nonexistent") raises ArchetypeNotFoundError: PASS
  8. GET /api/archetypes returns 200 with four archetypes: PASS
  9. GET /api/archetypes/software_development returns 200: PASS
  10. GET /api/archetypes/nonexistent returns 404: PASS
  11. POST /api/projects with archetype populates knowledge: PASS
  12. POST /api/projects without archetype works as before: PASS
  13. POST /api/projects with invalid archetype returns 400: PASS
  14. Clone endpoint returns 201 with cloned archetype: PASS
  15. Cloned archetypes appear in GET /api/archetypes: PASS
  16. Clone with built-in name returns 409: PASS
- VERDICT: PASS

### [PM] 2026-03-15 14:15
- Reviewed diff: 14 files total (5 modified, 9 new)
  - Modified: core/project.py, api/app.py, api/routes/projects.py, db/models.py, tests/test_models.py
  - New: core/archetypes.py, api/routes/archetypes.py, api/schemas/archetype.py, archetypes/__init__.py, 4 YAML files, tests/test_archetypes.py
- Results verified: real data present
  - 21 tests pass in test_archetypes.py (8 unit loading, 4 unit application, 9 integration API)
  - 486 tests pass in full suite, 0 failures
  - Ruff clean
  - All four YAML archetypes load correctly with valid role references
  - API endpoints return correct status codes and payloads (verified by running tests)
- Acceptance criteria: all 16 met
  1. 12+ tests: PASS (21 tests)
  2. Four YAML files exist: PASS
  3. All required fields present: PASS
  4. Role references valid: PASS (all map to existing roles in backend/codehive/roles/)
  5. list_builtin_archetypes sorted: PASS
  6. load_archetype returns correct ArchetypeDefinition: PASS
  7. load_archetype nonexistent raises: PASS
  8. GET /api/archetypes 200: PASS
  9. GET /api/archetypes/{name} 200: PASS
  10. GET /api/archetypes/nonexistent 404: PASS
  11. POST /api/projects with archetype populates knowledge: PASS
  12. POST /api/projects without archetype unchanged: PASS
  13. POST /api/projects invalid archetype 400: PASS
  14. Clone endpoint 201: PASS
  15. Cloned archetypes in listing: PASS
  16. Clone with built-in name 409: PASS
- Code quality: clean, follows established patterns from issue #25 (roles). ArchetypeDefinition model mirrors RoleDefinition. set_builtin_dir/reset_builtin_dir for test isolation. CustomArchetype DB model mirrors CustomRole. API routes follow same structure as roles routes.
- Follow-up issues created: none needed
- VERDICT: ACCEPT
