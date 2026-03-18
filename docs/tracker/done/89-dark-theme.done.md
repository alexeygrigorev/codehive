# Issue #89: Add dark theme to web app

## Problem

The web app currently uses a light-only color scheme with hardcoded Tailwind color classes (e.g. `bg-white`, `bg-gray-50`, `text-gray-900`). Users working in low-light environments or who prefer dark interfaces have no option. The app should support both light and dark themes.

## Requirements

- [ ] Add dark mode CSS/Tailwind theme
- [ ] Theme toggle in the UI (header or settings)
- [ ] Persist theme preference in localStorage
- [ ] Respect system preference (`prefers-color-scheme: dark`) as default

## Scope

Web frontend only (`web/` directory). Mobile dark theme is tracked separately in #90.

## Dependencies

None. This is a standalone frontend issue.

## Implementation Notes

### Current State

- **Tailwind config** (`web/tailwind.config.js`): minimal config, no `darkMode` setting, no custom colors.
- **CSS** (`web/src/index.css`): only Tailwind directives, no custom CSS variables.
- **Components**: ~60 files use hardcoded light-theme Tailwind classes (`bg-white`, `bg-gray-50`, `bg-gray-100`, `text-gray-900`, `border-gray-200`, etc.) -- approximately 190 occurrences across 60 files.
- **Sidebar** (`Sidebar.tsx`): already uses a dark color scheme (`bg-gray-900`, `text-white`) so it needs minimal changes.
- **No existing theme infrastructure**: no theme context, no CSS variables, no dark mode classes.

### Approach

1. **Enable Tailwind dark mode**: set `darkMode: 'class'` in `tailwind.config.js` so that a `.dark` class on `<html>` activates dark variants.
2. **Create a `ThemeProvider` context** (`web/src/contexts/ThemeContext.tsx`):
   - On mount: check `localStorage` for saved preference; if none, check `window.matchMedia('(prefers-color-scheme: dark)')`.
   - Expose `theme` (`'light' | 'dark' | 'system'`), `resolvedTheme` (`'light' | 'dark'`), and `setTheme()`.
   - Apply/remove the `dark` class on `document.documentElement`.
   - Listen for system preference changes when in `'system'` mode.
3. **Add a `ThemeToggle` component**: a button in the header (in `MainLayout.tsx`) that cycles or switches between light/dark/system. Use an icon (sun/moon) or text label.
4. **Update all components**: add `dark:` variant classes alongside existing light classes. Key areas:
   - **MainLayout**: `bg-gray-50` -> `bg-gray-50 dark:bg-gray-900`
   - **Header**: `bg-white border-gray-200` -> `bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700`
   - **ProjectCard**: `bg-white border-gray-200` -> add dark variants
   - **MessageBubble**: each role style needs dark variants
   - **DiffViewer**: addition/deletion colors need dark variants
   - **ChatPanel, SearchBar, Sidebar, all sidebar panels, pages, modals, etc.**
5. **localStorage key**: `codehive-theme` (consistent with existing `codehive-sidebar-collapsed` pattern).

### Components requiring dark mode updates (all files with hardcoded light colors)

Layouts: `MainLayout.tsx`, `MobileLayout.tsx`
Pages: `DashboardPage`, `ProjectPage`, `SessionPage`, `SearchPage`, `LoginPage`, `RegisterPage`, `QuestionsPage`, `ReplayPage`, `NewProjectPage`, `NotFoundPage`
Components: `ProjectCard`, `MessageBubble`, `ToolCallResult`, `DiffViewer`, `DiffFileList`, `DiffModal`, `ChatPanel`, `ChatInput`, `SearchBar`, `Sidebar`, `Breadcrumb`, `UserMenu`, `ExportButton`, `SessionList`, `IssueList`, `SessionModeSwitcher`, `SessionModeIndicator`, `ApprovalPrompt`, `ApprovalBadge`, `SessionApprovalBadge`, `SubAgentTree`, `SubAgentNode`, `AggregatedProgress`, `QuestionCard`, `CheckpointList`, `CheckpointCreate`, `RoleList`, `RoleEditor`, `RoleAssigner`, `ReplayTimeline`, `ReplayControls`, `ReplayStep`, `VoiceButton`, `TranscriptPreview`, `RecordingOverlay`, `AudioWaveform`, `AgentMessageItem`, `ProtectedRoute`
Sidebar panels: `TodoPanel`, `ChangedFilesPanel`, `TimelinePanel`, `SubAgentPanel`, `QuestionsPanel`, `CheckpointPanel`, `SidebarTabs`, `AgentCommPanel`, `ActivityPanel`
Mobile: `MobileNav`, `QuickActions`, `DiffSummary`, `MobileSessionHeader`
Search: `SearchHighlight`, `SearchResult`
Project flow: `FlowChat`, `BriefReview`

## Acceptance Criteria

- [ ] `darkMode: 'class'` is configured in `web/tailwind.config.js`
- [ ] A `ThemeProvider` context exists that manages theme state (light/dark/system)
- [ ] On first load with no localStorage value, the theme follows the system preference (`prefers-color-scheme`)
- [ ] A theme toggle button is visible in the header area of `MainLayout`
- [ ] Clicking the toggle switches between light and dark (and optionally system)
- [ ] The selected theme preference is persisted in `localStorage` under `codehive-theme`
- [ ] Reloading the page restores the previously selected theme
- [ ] All pages and components render with appropriate dark colors when dark mode is active -- no white/light backgrounds bleeding through
- [ ] The DiffViewer shows appropriate dark-mode colors for additions (green) and deletions (red) that remain readable
- [ ] MessageBubble role styles have dark variants that are visually distinct per role
- [ ] The Sidebar remains visually consistent (it is already dark-themed)
- [ ] No accessibility regressions: text contrast ratios remain adequate in both themes
- [ ] All existing tests continue to pass: `cd web && npx vitest run`
- [ ] New tests are added for: ThemeProvider, ThemeToggle, and dark-mode rendering of at least 3 key components (e.g., MainLayout, MessageBubble, ProjectCard)
- [ ] `cd web && npx vitest run` passes with all new tests (8+ new tests minimum)

## Test Scenarios

### Unit: ThemeProvider context
- Default theme is `system` when no localStorage value exists
- When system preference is dark, `resolvedTheme` is `dark` and `document.documentElement` has class `dark`
- When system preference is light, `resolvedTheme` is `light` and no `dark` class
- `setTheme('dark')` adds `dark` class and stores `dark` in localStorage
- `setTheme('light')` removes `dark` class and stores `light` in localStorage
- `setTheme('system')` follows the system preference and stores `system` in localStorage
- Changing system preference while in `system` mode updates the resolved theme

### Unit: ThemeToggle component
- Renders a toggle button in the DOM
- Clicking the toggle changes the theme (verified via context or class on documentElement)
- Displays appropriate icon/label for current theme state

### Unit: Dark-mode rendering
- MainLayout: when `dark` class is on html, background uses dark color (check for `dark:bg-` class presence)
- MessageBubble: each role (user, assistant, system, tool) has `dark:` variant classes
- ProjectCard: has dark background and border classes
- DiffViewer: addition and deletion lines have dark-mode color classes

### Integration: Theme persistence
- Set theme to dark, simulate page reload (re-render provider), verify dark mode persists
- Set theme to light, simulate page reload, verify light mode persists
- Clear localStorage, verify system preference is used as fallback

## Log

### [SWE] 2026-03-18 13:30
- Implemented complete dark theme support for the web app
- **Infrastructure**:
  - Added `darkMode: 'class'` to `web/tailwind.config.js`
  - Created `web/src/context/ThemeContext.tsx` with ThemeProvider, useTheme hook (light/dark/system support, localStorage persistence under `codehive-theme`, system preference detection via matchMedia, listener for system preference changes)
  - Created `web/src/components/ThemeToggle.tsx` (cycles through light/dark/system, shows Sun/Moon/Auto labels)
  - Wrapped App with ThemeProvider in `web/src/App.tsx`
  - Added ThemeToggle to MainLayout header
- **Component updates** (added `dark:` variant classes to all ~60 files):
  - Layouts: MainLayout, MobileLayout
  - Pages: DashboardPage, ProjectPage, SessionPage, SearchPage, LoginPage, RegisterPage, QuestionsPage, ReplayPage, NewProjectPage, NotFoundPage, RolesPage
  - Components: ProjectCard, MessageBubble, ToolCallResult, DiffViewer, DiffFileList, DiffModal, ChatPanel, ChatInput, SearchBar, Sidebar (already dark - no changes needed), Breadcrumb, UserMenu (already dark - no changes needed), ExportButton, SessionList, IssueList, SessionModeSwitcher, SessionModeIndicator (badge colors - no changes needed), ApprovalPrompt, ApprovalBadge (no changes needed), SessionApprovalBadge (no changes needed), SubAgentTree (no changes needed), SubAgentNode, AggregatedProgress, QuestionCard, CheckpointList, CheckpointCreate, RoleList, RoleEditor, RoleAssigner, ReplayTimeline, ReplayControls, ReplayStep, VoiceButton, TranscriptPreview, RecordingOverlay, AudioWaveform (canvas - no changes needed), AgentMessageItem, ProtectedRoute, SessionHistorySearch
  - Sidebar panels: SidebarTabs, TodoPanel, ChangedFilesPanel, TimelinePanel, SubAgentPanel, QuestionsPanel, CheckpointPanel, AgentCommPanel, ActivityPanel
  - Mobile: MobileNav, QuickActions, DiffSummary, MobileSessionHeader
  - Search: SearchResult, SearchHighlight (no changes needed)
  - Project flow: FlowChat, BriefReview
- **Tests**: Fixed existing tests (App.test.tsx, AppAuth.test.tsx) that render MainLayout to wrap with ThemeProvider
- Files modified: 55 files across web/src/
- Tests added: 25 new tests across 3 test files (ThemeContext.test.tsx, ThemeToggle.test.tsx, DarkMode.test.tsx)
- Build results: 592 tests pass, 0 fail, TypeScript compiles cleanly
- Known limitations: None

### [QA] 2026-03-18 13:35
- TypeScript: compiles cleanly (npx tsc -b)
- Tests: 592 passed, 0 failed (npx vitest run)
- New tests: 25 tests across 3 files (ThemeContext.test.tsx: 8, ThemeToggle.test.tsx: 3, DarkMode.test.tsx: 14)
- Acceptance criteria:
  - `darkMode: 'class'` configured in tailwind.config.js: PASS
  - ThemeProvider context exists with light/dark/system: PASS
  - First load with no localStorage follows system preference: PASS
  - Theme toggle button visible in MainLayout header: PASS
  - Toggle cycles between light/dark/system: PASS
  - Preference persisted in localStorage under `codehive-theme`: PASS
  - Reloading restores previously selected theme: PASS (tested via unmount/remount)
  - All components have dark: variants (no light backgrounds bleeding): PASS (55 files updated)
  - DiffViewer dark-mode colors for additions/deletions: PASS (dark:bg-green-900/30, dark:bg-red-900/30)
  - MessageBubble role styles have dark variants: PASS (user/assistant/system/tool all covered)
  - Sidebar remains consistent (already dark-themed): PASS (no changes needed)
  - Text contrast remains adequate: PASS (reasonable dark color choices throughout)
  - All existing tests pass: PASS (592 total)
  - New tests for ThemeProvider, ThemeToggle, dark-mode rendering: PASS (25 tests, covers MainLayout, MessageBubble, ProjectCard, DiffViewer, persistence)
  - 8+ new tests minimum: PASS (25 new tests)
- VERDICT: PASS

### [PM] 2026-03-18 14:10
- Reviewed diff: 61 files changed, 271 insertions, 259 deletions
- Results verified: real data present -- 592 tests pass (25 new), TypeScript compiles cleanly, QA confirmed all 14 acceptance criteria individually
- Implementation review:
  - ThemeContext.tsx: clean implementation with light/dark/system support, localStorage persistence under `codehive-theme`, matchMedia listener for system preference changes, proper cleanup on unmount
  - ThemeToggle.tsx: cycles light->dark->system with Sun/Moon/Auto labels, includes data-testid and aria-label
  - tailwind.config.js: `darkMode: 'class'` correctly configured
  - App.tsx: ThemeProvider wraps AuthProvider (correct ordering)
  - ~55 component files updated with `dark:` Tailwind variants -- consistent pattern throughout
  - DiffViewer: dark:bg-green-900/30 and dark:bg-red-900/30 with readable text colors
  - MessageBubble: all 4 roles (user/assistant/system/tool) have distinct dark variants
  - Sidebar: already dark-themed, no changes needed (correct decision)
- Tests are meaningful: ThemeContext tests (8) cover default state, system preference detection, setTheme behavior, localStorage persistence, and matchMedia listener; ThemeToggle tests (3) cover rendering, label display, and cycle behavior; DarkMode tests (14) verify dark: classes on MainLayout, MessageBubble (all roles), ProjectCard, DiffViewer (additions/deletions), and theme persistence across remounts
- No over-engineering: straightforward class-based dark mode with Tailwind, no CSS variables or complex abstractions
- Acceptance criteria: all 14 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
