# 25: Agent Roles

## Description
Implement the agent role system. Roles define agent behavior: responsibilities, allowed tools, coding rules, and task types. Support global roles (workspace-level) with simple per-project overrides. Roles are stored as YAML/JSON and loaded at session creation.

## Scope
- `backend/codehive/core/roles.py` -- Role loading, validation, merging (global + project override)
- `backend/codehive/roles/` -- Built-in role definitions as YAML files (developer, tester, product_manager, research_agent, bug_fixer, refactor_engineer)
- `backend/codehive/api/routes/roles.py` -- CRUD endpoints for custom roles
- `backend/codehive/engine/native.py` -- Extend to apply role constraints (tool filtering, system prompt from role definition)
- `backend/tests/test_roles.py` -- Role loading and constraint tests

## Role definition format (YAML)
```yaml
name: Developer
description: Implements features, modifies code, writes tests
responsibilities: [implement features, write tests, fix bugs]
allowed_tools: [edit_file, read_file, run_shell, git_commit, search_files]
coding_rules: [use type hints, write docstrings]
```

## Dependencies
- Depends on: #09 (engine adapter for tool filtering)
- Depends on: #03 (DB models for storing custom roles)
