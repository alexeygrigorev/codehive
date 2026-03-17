# Issue #88: Remove auth and workspaces -- simplify for single-user

**Status: SPLIT into sub-issues. Do not implement this file directly.**

## Problem

The app has a full JWT auth system and multi-workspace/multi-user model, but this is a self-hosted single-user tool. Auth adds friction (login screen, token management) and workspaces add unnecessary complexity (every project needs a workspace_id, workspace CRUD, workspace members).

## Sub-Issues

This issue was split into two parts because the combined scope touches 60+ files across backend, frontend, and mobile. The split also creates a clean dependency chain: auth bypass first, then workspace removal.

1. **#88a — Disable auth by default** (`88a-disable-auth.groomed.md`)
   - Add `CODEHIVE_AUTH_ENABLED=false` config flag
   - Bypass JWT checks, skip login screen, bypass permissions
   - Keep all auth code in place, just bypassed
   - No database changes

2. **#88b — Remove workspaces** (`88b-remove-workspaces.groomed.md`)
   - Depends on #88a being done first
   - Alembic migration to drop workspace tables and columns
   - Delete workspace models, routes, schemas, permission checks
   - Projects become top-level (no workspace_id)
   - Update 57+ backend files, 6+ frontend files

## Completion

This parent issue is complete when both #88a and #88b are `.done.md`.

## Notes

- Breaking DB change in #88b -- needs Alembic migration
- Don't delete auth code (#88a), just bypass with config flag
- The workspace concept can be re-added later if multi-tenancy is needed
