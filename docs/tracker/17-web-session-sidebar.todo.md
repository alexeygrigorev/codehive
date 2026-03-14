# 17: Web Session Sidebar

## Description
Build the session view sidebar panels: ToDo list with live progress, changed files list, sub-agent tree (placeholder), and action timeline. These panels provide context alongside the main chat.

## Scope
- `web/src/components/sidebar/TodoPanel.tsx` -- Task queue display with status indicators and progress
- `web/src/components/sidebar/ChangedFilesPanel.tsx` -- List of files modified in the session
- `web/src/components/sidebar/TimelinePanel.tsx` -- Chronological log of agent actions
- `web/src/components/sidebar/SubAgentPanel.tsx` -- Placeholder tree view for sub-agents (populated in #23)
- `web/src/components/sidebar/SidebarTabs.tsx` -- Tab navigation between sidebar panels
- `web/src/api/tasks.ts` -- API hooks for task queue
- `web/src/api/events.ts` -- API hooks for timeline events

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #06 (task queue API)
- Depends on: #07 (event bus for timeline data)
