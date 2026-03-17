# Issue #95: Web project page redesign — sessions, issues, and sub-agents

## Problem

The project page currently only shows a list of sessions. But a project has more structure:

- **Sessions** — active agent conversations (with sub-agent trees)
- **Issues** — task tracker per project (todo/in-progress/done)
- **Sub-agents** — sessions can spawn child sessions, forming a tree

None of this is visible in the web UI. The user can't see what's being worked on, what's queued, or how agents relate to each other.

## Requirements

### Project page layout
- [ ] Tabbed or sectioned layout: Sessions | Issues | Settings
- [ ] Sessions tab: list of sessions with status badges (idle, executing, blocked, completed)
- [ ] Issues tab: list of project issues with status (todo, in-progress, done), filterable
- [ ] Each session row shows: name, status, engine, mode, created_at, sub-agent count

### Session detail
- [ ] Chat view with message history (existing)
- [ ] Sub-agent tree: show parent → child session hierarchy
- [ ] Tool call timeline: what the agent did, in order
- [ ] Changed files panel: diffs accumulated by the session

### Issues panel
- [ ] List issues for the project (from /api/projects/{id}/issues)
- [ ] Status filters: all, open, in-progress, done
- [ ] Click to view issue details
- [ ] Create new issue from the UI

### Session creation
- [ ] "New Session" button (already added)
- [ ] Option to link session to an issue
- [ ] Option to select engine (native/claude_code) and mode

## Notes

- The backend already has all these APIs: sessions with sub-agents, issues CRUD, diffs, events
- This is primarily a frontend issue — wiring existing APIs into the UI
- Start with the project page layout and sessions list, then add issues and sub-agents
- Keep it simple — no drag-and-drop, no kanban boards, just clean lists with status badges
