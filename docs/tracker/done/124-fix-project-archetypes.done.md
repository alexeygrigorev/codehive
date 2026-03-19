# Issue #124: Fix project archetype cards on New Project page

## Problem

On the New Project page (`/projects/new`), there are 5 project creation options: Empty Project, Brainstorm, Guided Interview, From Notes, and From Repository. Only "Empty Project" works. Clicking any of the other 4 cards calls `startFlow()` which hits the backend `POST /api/project-flow/start` endpoint. The backend code exists (`backend/codehive/core/project_flow.py`) and handles all flow types, but users see errors or broken UI because the flow chat/review components have never been tested end-to-end and the backend uses in-memory state that resets on restart.

This issue is NOT about building full AI-powered flows. It is about making the UI honest: cards that do not work should say "Coming soon" so users are not confused.

## Decision: Scope

After reviewing the codebase:

1. **Brainstorm, Guided Interview, From Notes** -- These flows require a working LLM integration (the `generate_brief` function is a stub that builds a deterministic brief, but the actual chat-with-AI flow in FlowChat.tsx needs a real session engine). These are deferred. Mark as "Coming soon".

2. **From Repository** -- This connects to issue #126 (GitHub repo import). The current implementation calls `analyze_codebase()` which is a knowledge analyzer stub. The real "From Repository" feature is tracked in #126. Defer with "Coming soon".

3. **Empty Project** -- Already works. No changes needed.

All 4 non-working cards get a "Coming soon" badge and become non-clickable. This is honest UX.

## User Stories

### Story: User sees which project creation options are available
1. User navigates to `/projects/new`
2. User sees 5 project creation options: Empty Project, Brainstorm, Guided Interview, From Notes, From Repository
3. The "Empty Project" card is fully interactive (can be clicked, expands the form)
4. The other 4 cards each display a "Coming soon" badge/label
5. The other 4 cards are visually dimmed or muted to indicate they are not yet available
6. Clicking any "Coming soon" card does nothing (no error, no navigation, no API call)

### Story: User creates an empty project (existing flow, unchanged)
1. User navigates to `/projects/new`
2. User clicks "Empty Project"
3. The directory path form expands
4. User types `/home/user/projects/myapp` in the directory path field
5. The name field auto-fills with "myapp"
6. User clicks "Create Project"
7. User is redirected to the project page

### Story: User on dark mode sees readable "Coming soon" badges
1. User has dark mode enabled
2. User navigates to `/projects/new`
3. All "Coming soon" badges are readable (sufficient contrast)
4. Dimmed cards are still legible, just clearly inactive

## Acceptance Criteria

- [ ] The 4 non-working flow cards (Brainstorm, Guided Interview, From Notes, From Repository) each show a visible "Coming soon" badge
- [ ] The "Coming soon" cards are visually distinguished from the active "Empty Project" card (dimmed/muted styling, e.g. reduced opacity or muted colors)
- [ ] Clicking a "Coming soon" card does NOT trigger any API call, navigation, or error
- [ ] The "Empty Project" card continues to work exactly as before (expand form, create project)
- [ ] Dark mode: "Coming soon" badges and dimmed cards have sufficient contrast to be readable
- [ ] No changes to the backend -- this is a frontend-only fix
- [ ] `cd web && npx vitest run` passes (no regressions)
- [ ] `cd web && npx tsc --noEmit` passes (no type errors)
- [ ] E2e tests pass confirming all stories above

## E2E Test Scenarios

### E2E: "Coming soon" badges are visible on deferred cards
- Preconditions: App running
- Steps:
  1. Navigate to `/projects/new`
  2. For each of the 4 flow cards (Brainstorm, Guided Interview, From Notes, From Repository):
     - Assert the card is visible
     - Assert a "Coming soon" text/badge is visible within the card
     - Assert the card has a visual indicator of being disabled (e.g. `opacity` CSS, `pointer-events: none`, or a `disabled` attribute)
- Assertions: All 4 cards show "Coming soon", none are fully interactive

### E2E: Clicking a "Coming soon" card does nothing
- Preconditions: App running
- Steps:
  1. Navigate to `/projects/new`
  2. Click the "Brainstorm" card
  3. Assert no navigation occurred (still on `/projects/new`)
  4. Assert no error message appeared
  5. Assert no loading spinner appeared
- Assertions: Page state unchanged after clicking deferred card

### E2E: "Empty Project" still works
- Preconditions: App running, backend API available
- Steps:
  1. Navigate to `/projects/new`
  2. Click "Empty Project"
  3. Assert the directory path form is visible
  4. Type `/tmp/test-project` in the directory path field
  5. Assert the project name field auto-fills with "test-project"
  6. Click "Create Project"
  7. Assert navigation to a project page (`/projects/{id}`)
- Assertions: Empty project creation flow works end-to-end

### E2E: Dark mode contrast for "Coming soon" cards
- Preconditions: App running
- Steps:
  1. Emulate dark color scheme
  2. Navigate to `/projects/new`
  3. Take screenshot
  4. Assert all 4 "Coming soon" badges are visible
  5. Assert "Empty Project" title is visible
- Assertions: All text readable in dark mode

## Implementation Notes

- In `web/src/pages/NewProjectPage.tsx`, add a `comingSoon: boolean` field to each item in `FLOW_TYPES`
- For coming-soon cards: render with `opacity-50 cursor-not-allowed` classes, add a small "Coming soon" span/badge, remove the `onClick` handler (or make it a no-op)
- Do NOT remove the backend flow code -- it will be used when these features are implemented later
- Do NOT remove the `FlowChat` or `BriefReview` components -- they will be needed later

## Dependencies

- None. This is a standalone UI fix.

## Related Issues

- #126 (GitHub repo import) -- will eventually make "From Repository" functional
- #125 (Project directory picker) -- related to project creation UX

## Log

### [SWE] 2026-03-19 01:15
- Added `comingSoon: true` to all 4 flow types in FLOW_TYPES array
- Changed flow cards from `<button>` to `<div>` with conditional onClick/role/tabIndex
- Coming-soon cards render with `opacity-50 cursor-not-allowed` classes, `aria-disabled="true"`, and no onClick handler
- Added "Coming soon" badge as a rounded pill (`bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300`)
- Empty Project card unchanged (still a `<button>`)
- Updated existing e2e test `new-project-dark-theme.spec.ts` to use data-testid selectors instead of `button` locators (since flow cards are now divs), and removed the "From Notes" click test that expanded the input section
- Updated unit tests: replaced 5 tests that expected startFlow calls with 6 coming-soon behavior tests
- Updated `NewProjectFlow.test.tsx` integration tests to verify coming-soon behavior instead of wizard flow
- Added `@/api/system` mock to both test files (required after #125 merge)
- Fixed pre-existing test bug from #125: "git init checkbox can be unchecked" test was unchecking before typing path (which resets gitInit via onChange) -- reordered to type path first, then uncheck
- Created e2e test file `project-archetypes-coming-soon.spec.ts` with 4 scenarios covering all acceptance criteria
- Files modified:
  - `web/src/pages/NewProjectPage.tsx` (FLOW_TYPES + card rendering)
  - `web/src/test/NewProjectPage.test.tsx` (updated tests + added coming-soon tests)
  - `web/src/test/NewProjectFlow.test.tsx` (replaced wizard flow tests with coming-soon tests)
  - `web/e2e/project-archetypes-coming-soon.spec.ts` (new e2e test file)
  - `web/e2e/new-project-dark-theme.spec.ts` (updated selectors for div cards)
- Tests added: 6 new unit tests for coming-soon behavior, 3 updated integration tests, 4 new e2e tests
- Build results: 672 unit tests pass, 0 fail; tsc --noEmit clean; 6 e2e tests pass (4 new + 2 existing dark theme)
- Screenshots:
  - `/tmp/124-coming-soon-light.png` - light mode showing all 4 badges
  - `/tmp/124-coming-soon-dark.png` - dark mode showing readable badges with good contrast
  - `/tmp/124-click-coming-soon.png` - after clicking coming-soon card, no change
  - `/tmp/124-empty-project-created.png` - empty project flow still works
- No backend changes
- Known limitations: none

### [QA] 2026-03-19 01:30
- Tests: 672 passed, 0 failed (vitest run)
- TypeScript: tsc --noEmit clean (no errors)
- Acceptance criteria:
  - 4 non-working flow cards show "Coming soon" badge: PASS (4 badges rendered, verified by unit test `getAllByText("Coming soon")` returning length 4)
  - "Coming soon" cards visually distinguished (dimmed/muted): PASS (opacity-50 + cursor-not-allowed classes applied; verified by unit test)
  - Clicking "Coming soon" card does NOT trigger API call/navigation/error: PASS (onClick is undefined for comingSoon cards; startFlow never called; verified by unit + e2e tests)
  - "Empty Project" card works as before: PASS (remains a button, form expands, createProject called with correct args; verified by unit tests)
  - Dark mode contrast for badges and cards: PASS (dark:bg-gray-700 dark:text-gray-300 on badges, dark:text-gray-100 on titles; e2e dark mode test verifies visibility)
  - No changes to the backend: PASS (backend diff belongs to issue #125, not #124; issue #124 changes are frontend-only)
  - vitest run passes: PASS (672/672)
  - tsc --noEmit passes: PASS (clean)
  - E2e tests confirming stories: PASS (4 e2e scenarios in project-archetypes-coming-soon.spec.ts + 2 existing dark theme tests updated)
- Code quality: comingSoon flag cleanly integrated into FLOW_TYPES array; conditional rendering is clear; aria-disabled for accessibility; data-testid attributes for testability
- VERDICT: PASS
