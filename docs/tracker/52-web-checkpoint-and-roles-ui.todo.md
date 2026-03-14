# 52: Web UI for Checkpoints and Roles

## Description
Build the web UI components for managing checkpoints (list, create, rollback) and agent roles (view, create, assign). These are the frontend counterparts to the checkpoint (#24) and roles (#25) backends.

## Scope
- `web/src/components/CheckpointList.tsx` -- List of session checkpoints with restore button
- `web/src/components/CheckpointCreate.tsx` -- Manual checkpoint creation UI
- `web/src/components/RoleList.tsx` -- List of available roles (global + project)
- `web/src/components/RoleEditor.tsx` -- Create/edit role definition
- `web/src/components/RoleAssigner.tsx` -- Assign role when creating a session or sub-agent
- `web/src/api/checkpoints.ts` -- API hooks for checkpoint operations
- `web/src/api/roles.ts` -- API hooks for role management

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #24 (checkpoint backend)
- Depends on: #25 (agent roles backend)
