# 152 — Git init checkbox UX: hide checkbox when directory already has git

## Problem

When creating a new project and selecting a directory that already has a `.git` folder, the "Initialize git repository" checkbox is still visible (unchecked, with "(already a git repo)" hint). This is confusing -- the user sees a control they cannot meaningfully interact with. If the directory is already a git repo, the checkbox should be replaced with a read-only indicator.

## Dependencies

None. This is a self-contained frontend UX change in `NewProjectPage.tsx`.

## Scope

- Frontend only (`web/src/pages/NewProjectPage.tsx`)
- Update existing vitest tests (`web/src/test/NewProjectPage.test.tsx`)
- Add Playwright e2e test
- No backend changes required (the `has_git` field already exists in the directory browser API response)

## User Stories

### Story 1: Developer selects a git-tracked directory from the browser

1. User opens `/projects/new`
2. User clicks "Empty Project" to expand the form
3. The directory browser shows subdirectories, some with a green "git" badge
4. User clicks a directory that has the "git" badge (e.g. "myrepo")
5. The path field updates to `/home/user/codehive/myrepo`
6. Instead of the "Initialize git repository" checkbox, the user sees a read-only indicator: a green badge/icon with text "Git repository detected" (or similar)
7. The checkbox is not visible -- the user cannot accidentally toggle it
8. The `git_init` value sent to `createProject` is `false`

### Story 2: Developer selects a non-git directory from the browser

1. User opens `/projects/new`
2. User clicks "Empty Project" to expand the form
3. User clicks a directory without a "git" badge (e.g. "new-project")
4. The path field updates
5. The "Initialize git repository" checkbox is visible and checked by default
6. User can uncheck it if they prefer not to initialize git
7. The `git_init` value sent to `createProject` matches the checkbox state

### Story 3: Developer switches from a git directory to a non-git directory

1. User selects a git directory from the browser -- the checkbox is hidden, indicator is shown
2. User then selects a non-git directory from the browser
3. The indicator disappears, the checkbox reappears (checked by default)

### Story 4: Developer manually types a path (no browser selection)

1. User opens the form and manually types a path like `/home/user/projects/something`
2. The "Initialize git repository" checkbox remains visible and checked (we have no way to know if the typed path has git without a backend call)
3. If the user had previously selected a git directory (indicator was showing), typing in the path field reverts to showing the checkbox

### Story 5: Developer selects a git directory and creates the project

1. User selects a git directory from the browser
2. The git indicator shows "Git repository detected"
3. User clicks "Create Project"
4. The `createProject` API is called with `git_init: false`
5. Project is created successfully, user is redirected

## Acceptance Criteria

- [ ] When a directory with `has_git: true` is selected from the browser, the git init checkbox (`data-testid="git-init-checkbox"`) is NOT in the DOM
- [ ] When a directory with `has_git: true` is selected, a read-only indicator element is shown with `data-testid="git-detected-indicator"` containing text like "Git repository detected"
- [ ] The indicator has green styling consistent with the existing git badge in the directory browser (green background, green text)
- [ ] When a non-git directory is selected from the browser, the checkbox is visible and checked by default (current behavior preserved)
- [ ] When switching from a git directory to a non-git directory, the indicator disappears and the checkbox reappears
- [ ] When the user manually edits the path input (types/clears), the checkbox reappears (current behavior: `gitInitAutoDisabled` resets)
- [ ] When a git directory is selected and the user clicks "Create Project", `createProject` is called with `git_init: false`
- [ ] `uv run vitest run` passes with all existing tests updated + new tests for the indicator behavior
- [ ] Playwright e2e test covers Story 1 (select git dir, verify indicator shown, checkbox hidden) and Story 2 (select non-git dir, verify checkbox shown)
- [ ] Screenshots taken via Playwright for both states (git detected vs. checkbox shown)

## Technical Notes

### Current Implementation (what to change)

In `NewProjectPage.tsx`, lines 548-572, the git init section currently always renders the checkbox:

```tsx
{/* Git init checkbox */}
<div className="flex items-center gap-2">
  <input id="git-init" type="checkbox" ... data-testid="git-init-checkbox" />
  <label htmlFor="git-init">Initialize git repository</label>
  {gitInitAutoDisabled && <span>(already a git repo)</span>}
</div>
```

The engineer should replace this with conditional rendering:

- When `gitInitAutoDisabled` is true: render an indicator element (no checkbox, no label-for-checkbox)
- When `gitInitAutoDisabled` is false: render the existing checkbox

The `handleSelectDirectory` function (line 292) already sets `gitInitAutoDisabled` correctly. The state management is already in place -- this is purely a rendering change.

### Suggested indicator markup

```tsx
{gitInitAutoDisabled ? (
  <div className="flex items-center gap-2" data-testid="git-detected-indicator">
    {/* green check icon or git icon */}
    <span className="text-sm text-green-700 dark:text-green-300 font-medium">
      Git repository detected
    </span>
  </div>
) : (
  <div className="flex items-center gap-2">
    <input id="git-init" type="checkbox" ... />
    <label htmlFor="git-init">Initialize git repository</label>
  </div>
)}
```

## Test Scenarios

### Unit: Vitest (web/src/test/NewProjectPage.test.tsx)

**Update existing test:**
- "selecting a directory with has_git unchecks the checkbox and shows indicator" -- update to verify the checkbox is NOT in the DOM and the `git-detected-indicator` test ID IS present

**New tests to add:**
- Selecting a git directory hides the checkbox and shows "Git repository detected" indicator (`data-testid="git-detected-indicator"`)
- Selecting a non-git directory shows the checkbox, no indicator present
- Switching from git directory to non-git directory: indicator disappears, checkbox reappears
- After selecting a git directory, manually typing in the path field restores the checkbox
- Creating a project after selecting a git directory sends `git_init: false`

### E2E: Playwright (web/e2e/git-init-checkbox-ux.spec.ts)

**Scenario: Git directory selected from browser**
- Precondition: Backend returns a directory listing with at least one `has_git: true` entry
- Steps: Open `/projects/new`, click "Empty Project", click the git directory entry
- Assertions: `git-detected-indicator` is visible, `git-init-checkbox` is not visible
- Screenshot: `/tmp/152-git-detected-indicator.png`

**Scenario: Non-git directory selected from browser**
- Precondition: Backend returns a directory listing with at least one `has_git: false` entry
- Steps: Open `/projects/new`, click "Empty Project", click the non-git directory entry
- Assertions: `git-init-checkbox` is visible and checked, `git-detected-indicator` is not visible
- Screenshot: `/tmp/152-git-checkbox-normal.png`

## Log

### [SWE] 2026-03-28 11:22
- Implemented conditional rendering in NewProjectPage.tsx: when `gitInitAutoDisabled` is true, the checkbox is replaced with a green "Git repository detected" indicator (SVG check icon + green text) with `data-testid="git-detected-indicator"`; when false, the original checkbox is shown with `data-testid="git-init-checkbox"`
- Updated existing unit test ("selecting a directory with has_git...") to verify checkbox is NOT in DOM and indicator IS present
- Added 5 new unit tests: (1) git dir hides checkbox shows indicator, (2) non-git dir shows checkbox no indicator, (3) switching git->non-git toggles correctly, (4) manually typing path after git selection restores checkbox, (5) creating project after git selection sends git_init: false
- Updated existing e2e test in directory-picker.spec.ts (E2E 2) to check for new indicator instead of old "(already a git repo)" text
- Created new e2e test file: web/e2e/git-init-checkbox-ux.spec.ts with 2 scenarios (git dir selected, non-git dir selected) including screenshots
- Files modified: web/src/pages/NewProjectPage.tsx, web/src/test/NewProjectPage.test.tsx, web/e2e/directory-picker.spec.ts
- Files created: web/e2e/git-init-checkbox-ux.spec.ts
- Build results: 749 tests pass, 0 fail, tsc --noEmit clean
- E2E tests: NOT RUN -- requires backend + frontend servers running

### [QA] 2026-03-28 11:24
- Tests: 751 passed, 1 failed (ProjectPage.test.tsx line 231 -- broken by out-of-scope changes to NewSessionDialog/ProjectPage)
- tsc --noEmit: clean
- Acceptance criteria:
  - [PASS] Git dir selected from browser -> checkbox hidden, indicator with data-testid="git-detected-indicator" shown with green styling
  - [PASS] Non-git dir selected -> checkbox visible and checked by default
  - [PASS] Switching git -> non-git toggles indicator/checkbox correctly
  - [PASS] Manual path edit restores checkbox (gitInitAutoDisabled resets)
  - [PASS] Git dir selected -> createProject called with git_init: false
  - [PASS] data-testid attributes: git-detected-indicator, git-init-checkbox present
  - [PASS] 5 unit tests covering new behavior (1 updated + 4 new)
  - [PASS] Playwright e2e test file created with 2 scenarios + screenshots
  - [PASS] Green styling (text-green-700/dark:text-green-300, green SVG icon) consistent with git badge
- Out-of-scope changes causing failure:
  - backend/codehive/core/orchestrator_service.py (issue #153 work)
  - web/src/components/NewSessionDialog.tsx (issue #153 work: orchestrator/sub-agent engine UI)
  - web/src/pages/ProjectPage.tsx (issue #153 work: engine mapping)
  - Deleted docs/tracker/151-agent-personalities-team.todo.md and 153-orchestrator-engine-selection.todo.md
  - These changes broke ProjectPage.test.tsx ("creates session with default values" expects old call signature)
- VERDICT: FAIL
- Issues:
  1. FAILING TEST: web/src/test/ProjectPage.test.tsx line 231 -- test expects `engine: "claude_code"` and `config: { provider: "claude", model: "claude-sonnet-4-6" }` but the code now sends different values due to NewSessionDialog/ProjectPage changes. The engineer must either update this test to match the new behavior or revert the out-of-scope changes.
  2. OUT-OF-SCOPE CHANGES: The diff includes significant changes to NewSessionDialog.tsx, ProjectPage.tsx, and orchestrator_service.py that belong to issue #153 (orchestrator engine selection), not issue #152. These should be reverted from this changeset and done in their own issue.
