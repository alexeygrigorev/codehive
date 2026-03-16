# 53b: Mobile Dashboard Screen

## Description
Build the main dashboard screen showing projects list with active session counts and color-coded status badges. Tapping a project navigates to its sessions list.

## Implementation Plan

### 1. Dashboard screen
- `mobile/src/screens/DashboardScreen.tsx` -- FlatList of projects
- Each item shows: project name, description (truncated), active session count, status badge
- Pull-to-refresh to reload project list
- Status badge colors: green (all idle/completed), yellow (sessions running), red (any failed)

### 2. Project sessions list
- `mobile/src/screens/ProjectSessionsScreen.tsx` -- FlatList of sessions for a project
- Each item shows: session name, mode, status badge, last activity timestamp
- Tapping a session navigates to session detail (53c)

### 3. Shared components
- `mobile/src/components/StatusBadge.tsx` -- colored dot + label for session status
- `mobile/src/components/ProjectCard.tsx` -- project list item
- `mobile/src/components/SessionCard.tsx` -- session list item

## Acceptance Criteria

- [ ] Dashboard screen loads and displays projects from the backend API
- [ ] Each project shows active session count and a color-coded status badge
- [ ] Pull-to-refresh reloads the project list
- [ ] Tapping a project navigates to its sessions list
- [ ] Sessions list shows session name, mode, status, and last activity
- [ ] Empty states shown when no projects or no sessions exist

## Test Scenarios

### Unit: Components
- Render StatusBadge with each status value, verify correct color
- Render ProjectCard with mock data, verify name and session count display
- Render SessionCard with mock data, verify mode and status display

### Integration: Dashboard data
- Load DashboardScreen with mocked API, verify project FlatList renders
- Tap a project, verify navigation to ProjectSessionsScreen

## Dependencies
- Depends on: #53a (scaffolding + API client)
