# Issue #117: Sidebar becomes unusable with many projects

## Problem

The sidebar lists all projects expanded, and with many projects (especially test artifacts from e2e tests), it takes up the entire screen height. The chat window becomes cramped or unusable because the sidebar pushes content down or takes too much space.

## Requirements

- [ ] Projects in sidebar should be collapsible (collapsed by default, expand on click)
- [ ] Only the active project is expanded
- [ ] Add a project count indicator (e.g., "Projects (12)")
- [ ] Consider: hide projects with no sessions, or add a filter/search
- [ ] Sidebar should be scrollable independently of the main content
- [ ] Consider a max-height for the project list with overflow scroll
- [ ] Option to collapse the entire sidebar to just icons

## Related

- #116 — e2e test isolation will reduce the number of junk test projects
- But the UX should also handle many real projects gracefully
