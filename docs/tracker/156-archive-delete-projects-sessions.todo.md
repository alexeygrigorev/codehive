# 156 — Archive/delete projects, delete sessions

## Problem
There's no way to remove projects or sessions from the UI. With many projects, the sidebar and dashboard get cluttered.

## Vision

### Projects: Archive → Delete
- **Archive**: soft-delete — project is hidden from sidebar/dashboard but data is preserved (sessions, tasks, issues, team)
- Archived projects are accessible from an "Archive" section
- From the archive, the user can **restore** (unarchive) or **permanently delete**
- Permanent delete removes the project and all related data from the database

### Sessions: Direct Delete
- Sessions can be deleted directly (hard delete)
- Confirmation dialog before deleting
- Deleting a session removes it and its messages/events from the database

## Acceptance criteria
- [ ] Project model gains `archived_at` (nullable datetime) field
- [ ] Archive project: sets `archived_at`, hides from sidebar/dashboard
- [ ] Unarchive project: clears `archived_at`, project reappears
- [ ] Permanent delete project: removes project + all related data (cascade)
- [ ] API: PATCH /api/projects/{id}/archive, PATCH /api/projects/{id}/unarchive, DELETE /api/projects/{id}
- [ ] Sidebar and dashboard filter out archived projects
- [ ] Archive section in UI (accessible from sidebar or settings)
- [ ] Delete session: DELETE /api/sessions/{id} removes session + messages + events
- [ ] Confirmation dialog before delete/archive actions
- [ ] Archived projects still queryable via API (e.g., GET /api/projects?include_archived=true)
