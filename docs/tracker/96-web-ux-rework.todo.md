# Issue #96: Web UX rework — navigation, layout, and overall experience

## Problem

The web UI was built feature-by-feature and lacks cohesive UX. Key issues:

- No consistent navigation (no back buttons, no breadcrumbs)
- No sidebar/nav showing projects and sessions
- Session page has no link back to the project
- Dashboard is just a flat list of projects with no context
- No clear visual hierarchy between project → sessions → chat
- Mode switcher, approval badges, history search are present but disorganized
- Timeline sidebar shows raw events that aren't useful to the user

## Requirements

### Navigation
- [ ] Persistent sidebar: projects list, collapsible to show sessions under each project
- [ ] Breadcrumb trail: Dashboard > Project Name > Session Name
- [ ] Click project name in sidebar to go to project page
- [ ] Click session in sidebar to go to session chat
- [ ] Current page highlighted in sidebar

### Dashboard
- [ ] Show projects with their active session count and last activity
- [ ] Quick-start: click a project → see sessions, click session → chat
- [ ] "New Project" prominent button

### Project page
- [ ] Tabs: Sessions | Issues
- [ ] Sessions list with status badges, "New Session" button
- [ ] Issues list with status filters (from #95)

### Session page
- [ ] Back to project link/breadcrumb
- [ ] Chat panel takes most of the space
- [ ] Collapsible sidebar with: tool calls, changed files
- [ ] Remove or hide the raw timeline — replace with a clean tool call log
- [ ] Streaming messages render as markdown

### General
- [ ] Consistent spacing, typography, colors
- [ ] Mobile-responsive (works on phone browser via SSH tunnel)
- [ ] Loading states and error handling throughout
- [ ] Dark theme support (from #89)

## Notes

- This is a large UX issue — consider breaking into sub-issues during grooming
- The backend APIs already support everything — this is pure frontend work
- Reference: the terminal TUI (`codehive code`) has a cleaner UX to draw from
