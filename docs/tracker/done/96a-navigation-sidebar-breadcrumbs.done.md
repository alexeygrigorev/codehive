# Issue #96a: Navigation sidebar with project/session tree and breadcrumbs

## Problem

The current `MainLayout` sidebar contains only a single "Dashboard" link. There is no way to navigate between projects and sessions without going back to the dashboard first. The session page has no breadcrumb or back link to its parent project.

### Current state

- `MainLayout.tsx` sidebar: static list with one item ("Dashboard")
- `ProjectPage.tsx`: has a manual "Back to Dashboard" link but no breadcrumb
- `SessionPage.tsx`: no back link, no project context shown
- No project/session tree anywhere in the navigation

## Scope

Add a navigation sidebar to `MainLayout` that shows a collapsible project/session tree, and add a breadcrumb trail to project and session pages. Pure frontend work -- all backend APIs already exist.

**In scope:**
1. Sidebar project list (fetched from `/api/projects`)
2. Collapsible session list under each project (fetched from `/api/projects/{id}/sessions`)
3. Current page highlighted in sidebar
4. Breadcrumb component: Dashboard > Project Name > Session Name
5. Breadcrumbs rendered on ProjectPage and SessionPage
6. Sidebar collapse/expand toggle (for more screen space on session page)

**Out of scope:**
- Project page content changes (covered by #95)
- Session page sidebar panels (covered by #96b)
- Mobile layout changes (MobileLayout has its own MobileNav)
- Dark theme (covered by #89)

## Dependencies

- None. Backend APIs exist: `GET /api/projects`, `GET /api/projects/{id}/sessions`

## Requirements

### 1. Sidebar project tree

- Fetch projects list on mount via `GET /api/projects`
- Show each project name as a clickable link to `/projects/{id}`
- Each project row has a chevron/toggle to expand and show its sessions
- When expanded, fetch sessions from `GET /api/projects/{id}/sessions` (cache per project, do not re-fetch on every toggle)
- Each session row links to `/sessions/{id}` and shows: name, status badge (small colored dot)
- Active page (current project or session) is visually highlighted (e.g. bold text, background color)
- Sidebar header still shows "Codehive" branding and UserMenu

### 2. Sidebar collapse

- A toggle button (hamburger or chevron) at the top of the sidebar
- When collapsed, sidebar shrinks to icon-width (e.g. 48px) showing only project initials or icons
- When expanded, shows the full project/session tree (width ~256px, matching current w-64)
- Collapse state persists in localStorage

### 3. Breadcrumb trail

- Create a `Breadcrumb` component that renders a trail like: Dashboard > Project Name > Session Name
- Each segment is a clickable link except the last (current page)
- Separator: ">" or "/" character
- Rendered inside the content area (below the top header bar, above page content)
- On `ProjectPage`: Dashboard > {project.name}
- On `SessionPage`: Dashboard > {project.name} > {session.name}
  - SessionPage must fetch project info to show the project name in the breadcrumb (session already has `project_id`)
- On `DashboardPage`: no breadcrumb (it's the root)

### 4. Styling

- Sidebar matches existing dark theme (bg-gray-900 text-white)
- Breadcrumbs use subtle gray text, small font size, consistent with existing Tailwind patterns
- Smooth expand/collapse transitions (CSS transition on width)

## Acceptance Criteria

- [ ] MainLayout sidebar shows a list of projects fetched from the API
- [ ] Clicking a project chevron expands to show its sessions
- [ ] Clicking a project name navigates to the project page
- [ ] Clicking a session name navigates to the session page
- [ ] Current page (project or session) is visually highlighted in the sidebar
- [ ] Sidebar has a collapse/expand toggle; collapsed state shows minimal width
- [ ] Collapse state persists across page loads (localStorage)
- [ ] ProjectPage shows breadcrumb: Dashboard > Project Name
- [ ] SessionPage shows breadcrumb: Dashboard > Project Name > Session Name
- [ ] Breadcrumb segments (except current page) are clickable links
- [ ] DashboardPage shows no breadcrumb
- [ ] `cd web && npx vitest run` passes with tests for Breadcrumb and sidebar tree
- [ ] No TypeScript errors: `cd web && npx tsc --noEmit` passes
- [ ] Existing tests still pass

## Test Scenarios

### Unit: Breadcrumb component
- Renders single segment (project page): "Dashboard > Project Name" with Dashboard as link
- Renders two segments (session page): "Dashboard > Project > Session" with Dashboard and Project as links
- Current (last) segment is plain text, not a link
- Renders nothing when given empty segments

### Unit: Sidebar project tree
- Renders list of projects fetched from API
- Clicking expand toggle shows session list under the project
- Sessions show name and status dot
- Active project is highlighted when on its page
- Active session is highlighted when on its page
- Collapsed sidebar shows narrow width

### Integration: MainLayout navigation
- Clicking a project in sidebar navigates to `/projects/{id}`
- Clicking a session in sidebar navigates to `/sessions/{id}`
- Sidebar project list updates when projects are added (e.g. after creating a new project and navigating back)

## Notes

- The `fetchProjects` and `fetchSessions` API functions already exist in `web/src/api/`
- Sessions already have `project_id` so the breadcrumb can fetch the parent project
- Keep the sidebar responsive -- do not break the MobileLayout (it uses a separate component)
- This is a single-user self-hosted tool -- no need for workspace switching or multi-user features

## Log

### [SWE] 2026-03-18 11:29
- Created Sidebar component with collapsible project/session tree, localStorage-persisted collapse state, status dots, active page highlighting
- Created Breadcrumb component with clickable link segments and aria-current on last segment
- Updated MainLayout to use new Sidebar component (replaced static sidebar)
- Updated ProjectPage to show breadcrumb (Dashboard > Project Name), replacing old "Back to Dashboard" link
- Updated SessionPage to show breadcrumb (Dashboard > Project Name > Session Name), fetching parent project for breadcrumb context
- Updated existing ProjectPage tests to use getByRole("heading") since project name now appears in both breadcrumb and h1
- Files created: web/src/components/Sidebar.tsx, web/src/components/Breadcrumb.tsx, web/src/test/Breadcrumb.test.tsx, web/src/test/Sidebar.test.tsx
- Files modified: web/src/layouts/MainLayout.tsx, web/src/pages/ProjectPage.tsx, web/src/pages/SessionPage.tsx, web/src/test/ProjectPage.test.tsx
- Tests added: 17 new tests (5 Breadcrumb, 12 Sidebar)
- Build results: 514 tests pass, 0 fail, tsc clean
- Known limitations: none

### [QA] 2026-03-18 12:15
- Tests: 567 passed, 0 failed (all tests including 17 new Sidebar + Breadcrumb tests)
- TypeScript: `tsc -b` clean
- ESLint: clean on all changed files
- Acceptance criteria:
  - MainLayout sidebar shows a list of projects fetched from the API: PASS
  - Clicking a project chevron expands to show its sessions: PASS
  - Clicking a project name navigates to the project page: PASS
  - Clicking a session name navigates to the session page: PASS
  - Current page (project or session) is visually highlighted in the sidebar: PASS
  - Sidebar has a collapse/expand toggle; collapsed state shows minimal width: PASS
  - Collapse state persists across page loads (localStorage): PASS
  - ProjectPage shows breadcrumb: Dashboard > Project Name: PASS
  - SessionPage shows breadcrumb: Dashboard > Project Name > Session Name: PASS
  - Breadcrumb segments (except current page) are clickable links: PASS
  - DashboardPage shows no breadcrumb: PASS
  - `cd web && npx vitest run` passes with tests for Breadcrumb and sidebar tree: PASS
  - No TypeScript errors: `cd web && npx tsc --noEmit` passes: PASS
  - Existing tests still pass: PASS
- VERDICT: PASS
