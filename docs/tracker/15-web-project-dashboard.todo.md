# 15: Web Project Dashboard

## Description
Build the project list and per-project dashboard pages in the web app. Show all projects with their active sessions, recent issues, and status indicators.

## Scope
- `web/src/pages/DashboardPage.tsx` -- List of all projects with status summaries
- `web/src/pages/ProjectPage.tsx` -- Single project view: active sessions, issues, settings
- `web/src/components/ProjectCard.tsx` -- Project summary card component
- `web/src/components/SessionList.tsx` -- List of sessions within a project
- `web/src/api/projects.ts` -- API hooks for project CRUD
- `web/src/api/sessions.ts` -- API hooks for session listing

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #04 (project CRUD API)
- Depends on: #05 (session CRUD API)
