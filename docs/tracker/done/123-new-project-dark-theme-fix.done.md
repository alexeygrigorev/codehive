# Issue #123: New Project page titles look bad in dark theme

## Problem

On the New Project page (`/projects/new`), several card titles and labels are missing `dark:` text color variants. They inherit the default black text color, which is invisible or very hard to read against the dark backgrounds.

## Root Cause Analysis

In `web/src/pages/NewProjectPage.tsx`, three elements lack `dark:text-*` classes:

1. **Line 165** -- "Empty Project" card title: `<h3 className="font-semibold text-lg">` has no `dark:text-gray-100`
2. **Line 235** -- Flow type card titles (Brainstorm, Guided Interview, From Notes, From Repository): `<h3 className="font-semibold text-lg">` has no `dark:text-gray-100`
3. **Line 243** -- "Paste your notes" / "Repository URL" label: `<label className="block font-medium">` has no `dark:text-gray-200`

The `<p>` descriptions and inputs already have proper dark variants -- only the `<h3>` titles and this one `<label>` are affected.

## Scope

- **In scope**: Add missing `dark:` text color classes to `NewProjectPage.tsx`
- **Out of scope**: Other pages, layout-level dark mode issues, mobile-specific dark mode (tracked in #90)

## Dependencies

- None. Issue #89 (dark theme infrastructure) is already done.

## User Stories

### Story: Developer views New Project page in dark mode
1. User has dark mode enabled (via ThemeToggle or system preference)
2. User navigates to `/projects/new`
3. User sees the "Empty Project" card -- the title "Empty Project" is light-colored text (gray-100) readable against the dark background
4. User sees the four flow-type cards (Brainstorm, Guided Interview, From Notes, From Repository) -- all titles are light-colored text readable against the dark background
5. User clicks "From Notes" -- the label "Paste your notes" appears in light-colored text (gray-200) readable against the dark background
6. All text on the page has sufficient contrast in dark mode -- no black-on-dark-gray text anywhere

### Story: Developer views New Project page in light mode (no regression)
1. User has light mode enabled
2. User navigates to `/projects/new`
3. All card titles and labels are dark text on light background, same as before the fix
4. No visual regressions from adding dark: variants

## Acceptance Criteria

- [ ] "Empty Project" `<h3>` has `dark:text-gray-100` class
- [ ] All four flow-type card `<h3>` titles have `dark:text-gray-100` class
- [ ] "Paste your notes" / "Repository URL" `<label>` has `dark:text-gray-200` class
- [ ] Playwright screenshot of `/projects/new` in dark mode shows all titles readable (no black text on dark background)
- [ ] Playwright screenshot of `/projects/new` in light mode shows no regression
- [ ] `uv run vitest run` passes (existing dark mode unit tests still pass)
- [ ] `tsc --noEmit` clean

## E2E Test Scenarios

### E2E: New Project page dark mode contrast
- **Precondition**: App running, dark mode enabled via `page.emulateMedia({ colorScheme: 'dark' })` or by adding `dark` class to `<html>`
- **Steps**:
  1. Navigate to `/projects/new`
  2. Take screenshot (saved to `/tmp/123-new-project-dark.png`)
  3. Verify "Empty Project" title element has `dark:text-gray-100` in its class list
  4. Verify each flow card title element has `dark:text-gray-100` in its class list
  5. Click on "From Notes" card to reveal the input section
  6. Verify the label element has `dark:text-gray-200` in its class list
  7. Take screenshot of the expanded state (saved to `/tmp/123-new-project-dark-expanded.png`)
- **Assertions**: All title/label elements have appropriate `dark:text-*` classes; screenshots show readable text

### E2E: New Project page light mode no regression
- **Precondition**: App running, light mode
- **Steps**:
  1. Navigate to `/projects/new`
  2. Take screenshot (saved to `/tmp/123-new-project-light.png`)
- **Assertions**: Page renders correctly, no visual artifacts

## Files to Modify

- `web/src/pages/NewProjectPage.tsx` -- add 3 missing `dark:text-*` classes
- `web/e2e/new-project-dark-theme.spec.ts` -- new e2e test file for the scenarios above

## Log

### [SWE] 2026-03-19 00:18
- Added `dark:text-gray-100` to "Empty Project" h3 (line 165)
- Added `dark:text-gray-100` to flow-type card h3 titles (line 235)
- Added `dark:text-gray-200` to "Paste your notes" / "Repository URL" label (line 243)
- Created e2e test file with 2 scenarios: dark mode contrast verification and light mode regression check
- Files modified: `web/src/pages/NewProjectPage.tsx`
- Files created: `web/e2e/new-project-dark-theme.spec.ts`
- Build results: `tsc --noEmit` clean, vitest 645 tests pass (111 files), Playwright 2 e2e tests pass
- Screenshots taken:
  - `/tmp/123-new-project-dark.png` -- dark mode, all titles readable in light text
  - `/tmp/123-new-project-dark-expanded.png` -- dark mode with "Paste your notes" label visible
  - `/tmp/123-new-project-light.png` -- light mode, no regression
- Known limitations: none

### [QA] 2026-03-19 00:25
- Tests: vitest 645 passed (111 files), 0 failed
- tsc --noEmit: clean
- Ruff: clean (backend ruff check passed; format issue in test_claude_code_wrapper.py is from issue #121, not #123)
- Screenshots reviewed:
  - `/tmp/123-new-project-dark.png` -- dark mode: all 5 card titles ("Empty Project", "Brainstorm", "Guided Interview", "From Notes", "From Repository") display in light text, fully readable against dark background
  - `/tmp/123-new-project-light.png` -- light mode: all card titles display in dark text, no regressions
- Acceptance criteria:
  - "Empty Project" h3 has `dark:text-gray-100`: PASS (confirmed in diff, line 165)
  - Flow-type card h3 titles have `dark:text-gray-100`: PASS (confirmed in diff, line 235, applies to all 4 flow cards via map)
  - Label has `dark:text-gray-200`: PASS (confirmed in diff, line 243)
  - Dark mode screenshot shows all titles readable: PASS (verified visually)
  - Light mode screenshot shows no regression: PASS (verified visually)
  - vitest passes: PASS (645 tests, 0 failures)
  - tsc --noEmit clean: PASS
- VERDICT: PASS
