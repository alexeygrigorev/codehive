# 26: Project Archetypes

## Description
Implement project archetypes -- pre-defined templates for common project types. An archetype bundles roles, default settings, workflow definitions, and tech stack info. Archetypes are selectable at project creation time, clonable, and customizable.

## Scope
- `backend/codehive/core/archetypes.py` -- Archetype loading, selection, cloning logic
- `backend/codehive/archetypes/` -- Built-in archetype definitions as YAML (software_development, research, technical_operations, code_maintenance)
- `backend/codehive/api/routes/projects.py` -- Extend project creation to accept archetype parameter
- `backend/codehive/api/routes/archetypes.py` -- List/get/clone archetype endpoints
- `backend/tests/test_archetypes.py` -- Archetype loading and application tests

## Dependencies
- Depends on: #25 (agent roles, since archetypes bundle roles)
- Depends on: #04 (project CRUD API)
