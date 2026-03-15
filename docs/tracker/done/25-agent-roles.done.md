# 25: Agent Roles

## Description
Implement the agent role system. Roles define agent behavior: responsibilities, allowed tools, coding rules, and task types. Support global roles (workspace-level) with simple per-project overrides. Roles are stored as YAML files and loaded at session creation. Custom roles can be created via the API.

## Scope
- `backend/codehive/core/roles.py` -- Role model (Pydantic), loading from YAML, validation, merging (global + project override)
- `backend/codehive/roles/` -- Built-in role definitions as YAML files (developer, tester, product_manager, research_agent, bug_fixer, refactor_engineer)
- `backend/codehive/api/routes/roles.py` -- CRUD endpoints for custom roles (stored in DB as JSONB)
- `backend/codehive/api/schemas/role.py` -- Pydantic request/response schemas for roles API
- `backend/codehive/engine/native.py` -- Extend `send_message` to accept a role, apply role constraints (tool filtering, system prompt injection from role definition)
- `backend/tests/test_roles.py` -- Role loading, validation, merging, API, and engine integration tests

## Role Definition Format (YAML)

```yaml
name: developer
display_name: Developer
description: Implements features, modifies code, writes tests
responsibilities:
  - implement features
  - write tests
  - fix bugs
allowed_tools:
  - edit_file
  - read_file
  - run_shell
  - git_commit
  - search_files
denied_tools: []
coding_rules:
  - use type hints
  - write docstrings
system_prompt_extra: |
  You are a developer agent. Focus on writing clean, well-tested code.
  Always use type hints and include docstrings.
```

## Role Resolution Logic

1. Load the global role definition from `backend/codehive/roles/{role_name}.yaml`
2. If a project-level override exists (stored in the project's `knowledge` JSONB under key `role_overrides.{role_name}`), merge it on top of the global definition (project fields override global fields, lists are replaced not appended)
3. If the role name is not found as a built-in, look it up in the DB (custom roles)
4. Return a validated `RoleDefinition` Pydantic model

## Engine Integration

When `NativeEngine.send_message` receives a role (via session config or explicit parameter):
- Filter `TOOL_DEFINITIONS` to only include tools listed in `allowed_tools` (if specified); remove tools listed in `denied_tools`
- Prepend `system_prompt_extra` from the role to the system prompt
- Include `coding_rules` in the system prompt as formatted rules
- The orchestrator mode constraints still take priority (orchestrator + role = intersection of allowed tools)

## Dependencies
- Depends on: #09 (engine adapter for tool filtering) -- DONE
- Depends on: #03 (DB models for storing custom roles in JSONB) -- DONE

## Acceptance Criteria

- [ ] `RoleDefinition` Pydantic model in `backend/codehive/core/roles.py` with fields: name, display_name, description, responsibilities, allowed_tools, denied_tools, coding_rules, system_prompt_extra -- all with sensible defaults
- [ ] Six built-in YAML role files exist under `backend/codehive/roles/`: `developer.yaml`, `tester.yaml`, `product_manager.yaml`, `research_agent.yaml`, `bug_fixer.yaml`, `refactor_engineer.yaml`
- [ ] `load_role(role_name)` loads and validates a built-in role from YAML, returns `RoleDefinition`
- [ ] `load_role(role_name)` raises `RoleNotFoundError` for unknown role names
- [ ] `merge_role(global_role, project_overrides)` returns a new `RoleDefinition` with project-level fields overriding global fields; list fields (allowed_tools, coding_rules, responsibilities) are replaced, not appended
- [ ] `list_builtin_roles()` returns names of all built-in YAML roles
- [ ] API: `GET /api/roles` returns all available roles (built-in + custom)
- [ ] API: `GET /api/roles/{role_name}` returns a single role definition
- [ ] API: `POST /api/roles` creates a custom role, returns 201; rejects duplicate names with 409
- [ ] API: `PUT /api/roles/{role_name}` updates a custom role; rejects updates to built-in roles with 403
- [ ] API: `DELETE /api/roles/{role_name}` deletes a custom role; rejects deletion of built-in roles with 403
- [ ] API: `GET /api/projects/{project_id}/roles/{role_name}` returns the resolved role (global merged with project overrides)
- [ ] `NativeEngine.send_message` filters tools based on role `allowed_tools` and `denied_tools` when a role is present in session config
- [ ] `NativeEngine.send_message` prepends role `system_prompt_extra` and `coding_rules` to the system prompt when a role is present
- [ ] When both orchestrator mode and a role are active, tool filtering uses the intersection (orchestrator allowed AND role allowed)
- [ ] `uv run pytest backend/tests/test_roles.py -v` passes with 15+ tests

## Test Scenarios

### Unit: Role Loading and Validation
- Load each of the 6 built-in roles from YAML, verify all fields parse correctly
- Load a role with missing optional fields, verify defaults apply
- Attempt to load a nonexistent role, verify `RoleNotFoundError`
- Validate that a role with an empty `name` field is rejected
- Validate YAML with invalid structure (e.g., `allowed_tools` is a string instead of list) is rejected

### Unit: Role Merging
- Merge a global role with empty overrides, verify global values are preserved
- Merge a global role with project overrides for `allowed_tools`, verify the override replaces (not appends) the global list
- Merge a global role with project overrides for `coding_rules` and `system_prompt_extra`, verify both are replaced
- Merge a global role with partial overrides (only `description`), verify other fields remain from global

### Unit: Tool Filtering from Role
- Given a role with `allowed_tools: [read_file, search_files]`, verify only those tools remain from TOOL_DEFINITIONS
- Given a role with `denied_tools: [git_commit]`, verify git_commit is removed and all others remain
- Given a role with both `allowed_tools` and `denied_tools`, verify denied takes priority
- Given a role with no allowed_tools set (empty or null), verify all tools are available

### Unit: System Prompt Construction from Role
- Given a role with `system_prompt_extra` and `coding_rules`, verify the constructed system prompt contains both
- Given a role with no `system_prompt_extra`, verify system prompt is not modified
- Verify coding rules are formatted as a numbered or bulleted list in the prompt

### Integration: API Endpoints
- `GET /api/roles` returns list including all 6 built-in roles
- `GET /api/roles/developer` returns the developer role with correct fields
- `GET /api/roles/nonexistent` returns 404
- `POST /api/roles` with valid body creates a custom role, returns 201
- `POST /api/roles` with duplicate name returns 409
- `PUT /api/roles/my_custom_role` updates the custom role
- `PUT /api/roles/developer` returns 403 (cannot modify built-in)
- `DELETE /api/roles/my_custom_role` returns 204
- `DELETE /api/roles/developer` returns 403 (cannot delete built-in)
- `GET /api/roles` after creating a custom role includes it alongside built-ins

### Integration: Engine with Roles
- Create a session with `config.role = "tester"`, send a message, verify only tester-allowed tools are passed to the API call
- Create a session in orchestrator mode with a role, verify tool set is the intersection of orchestrator-allowed and role-allowed tools
- Verify the system prompt includes role-specific content when a role is set

## Log

### [SWE] 2026-03-15 14:30
- Implemented the complete agent role system: core roles module, built-in YAML definitions, API CRUD endpoints, and engine integration
- Created `RoleDefinition` Pydantic model with all required fields and validation (name must not be empty)
- Created 6 built-in YAML role files: developer, tester, product_manager, research_agent, bug_fixer, refactor_engineer
- Implemented `load_role()`, `list_builtin_roles()`, `merge_role()`, `filter_tools_for_role()`, `build_role_system_prompt()`
- Role resolution: built-in YAML first, then custom roles from DB
- Merging: project overrides replace (not append) list fields
- Added `CustomRole` DB model with JSONB definition column
- API endpoints: GET/POST /api/roles, GET/PUT/DELETE /api/roles/{name}, GET /api/projects/{id}/roles/{name}
- Built-in roles protected: 403 on PUT/DELETE, 409 on duplicate POST
- Extended `NativeEngine.send_message` with `role` parameter (accepts string name or RoleDefinition)
- Engine applies role-based tool filtering and system prompt injection
- Orchestrator + role = intersection of allowed tool sets
- Added `pyyaml` as runtime dependency
- Files modified: backend/codehive/core/roles.py (new), backend/codehive/roles/*.yaml (6 new), backend/codehive/api/schemas/role.py (new), backend/codehive/api/routes/roles.py (new), backend/codehive/api/app.py, backend/codehive/engine/native.py, backend/codehive/db/models.py, backend/pyproject.toml, backend/tests/test_roles.py (new), backend/tests/test_models.py
- Tests added: 36 tests covering role loading (9), merging (4), tool filtering (4), system prompt (3), API (11), engine integration (5)
- Build results: 415 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 15:10
- Tests: 415 passed, 0 failed (36 in test_roles.py)
- Ruff: clean
- Format: clean
- Acceptance criteria:
  1. RoleDefinition Pydantic model with all fields and defaults: PASS
  2. Six built-in YAML role files (developer, tester, product_manager, research_agent, bug_fixer, refactor_engineer): PASS
  3. load_role(role_name) loads and validates built-in role from YAML: PASS
  4. load_role raises RoleNotFoundError for unknown names: PASS
  5. merge_role replaces list fields (not appends), returns new RoleDefinition: PASS
  6. list_builtin_roles() returns names of all built-in YAML roles: PASS
  7. GET /api/roles returns all available roles (built-in + custom): PASS
  8. GET /api/roles/{role_name} returns single role definition: PASS
  9. POST /api/roles creates custom role (201), rejects duplicates (409): PASS
  10. PUT /api/roles/{role_name} updates custom role, rejects built-in (403): PASS
  11. DELETE /api/roles/{role_name} deletes custom role, rejects built-in (403): PASS
  12. GET /api/projects/{project_id}/roles/{role_name} returns resolved merged role: PASS
  13. NativeEngine filters tools based on role allowed_tools and denied_tools: PASS
  14. NativeEngine prepends role system_prompt_extra and coding_rules to system prompt: PASS
  15. Orchestrator + role intersection for tool filtering: PASS
  16. 15+ tests passing in test_roles.py (actual: 36): PASS
- VERDICT: PASS

### [PM] 2026-03-15 15:35
- Reviewed diff: 8 files changed (6 new, 2 modified, plus 6 YAML role definitions)
- Core module: `backend/codehive/core/roles.py` -- RoleDefinition model, load/merge/filter/prompt functions, clean separation of concerns
- DB model: `CustomRole` with JSONB definition column, primary key on name
- API routes: full CRUD on `/api/roles`, project-scoped resolution on `/api/projects/{id}/roles/{name}`
- Engine integration: `NativeEngine.send_message` accepts `role` param, applies tool filtering and system prompt injection, orchestrator+role intersection correct
- 6 built-in YAML roles: developer, tester, product_manager, research_agent, bug_fixer, refactor_engineer -- all well-structured with distinct tool sets and prompts
- Results verified: 36 tests in test_roles.py all pass, 415 total tests pass, ruff clean
- Acceptance criteria: all 16 met
- Note: `GET /api/projects/{project_id}/roles/{role_name}` endpoint exists and is correct but has no automated test coverage. This is a minor gap -- the endpoint is straightforward and the underlying `merge_role` function is well-tested. Not blocking acceptance.
- Code quality: clean, well-documented, follows existing project patterns (same test fixture approach as other test files, consistent API schema style)
- No over-engineering, no under-building -- scope matches spec exactly
- VERDICT: ACCEPT
