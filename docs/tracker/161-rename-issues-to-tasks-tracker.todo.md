# 161 — Rename "Issues" to "Task Tracker" throughout the app

## Problem
The app uses "issues" as the name for trackable work items. This is confusing because:
1. "Issues" sounds like GitHub Issues — users might think it's a bug tracker
2. We already have GitHub integration that syncs actual GitHub issues
3. The pipeline kanban board calls them "tasks" but the API/model calls them "issues"

## Vision
Rename "issues" to "tasks" (or "tracker items") throughout:
- API endpoints: /api/issues → /api/tasks (or keep both for backward compat)
- Model: Issue → TrackerTask (or keep Issue internally but rename in UI/API)
- UI labels: "Issues" tab → "Task Tracker" tab
- Pipeline board already uses "tasks" — make it consistent

## Considerations
- This is a big rename — needs careful migration
- Keep backward-compatible API aliases during transition
- The existing `Task` model (session-scoped todo queue) conflicts — may need to rename that to `SessionTask` or merge them
- GitHub sync should still work (GitHub issues map to tracker tasks)

## Acceptance criteria
- [ ] UI consistently uses "Task Tracker" / "Tasks" instead of "Issues"
- [ ] API has consistent naming (decide on final naming)
- [ ] No confusion between GitHub Issues and internal tracker tasks
- [ ] Pipeline board and tracker use same terminology
- [ ] Backward-compatible API aliases if endpoints change
