# Issue #113: Session context usage tracking and progress bar

## Problem

Long coding sessions accumulate messages until they hit the model's context window limit, at which point the session breaks. There is no visibility into how much of the context window is being used. The existing UsagePanel shows cumulative token counts and cost, but does not show context window utilization (how full the current conversation is relative to the model's limit).

This is the foundation issue. It adds context window awareness (model limits lookup, per-request tracking of cumulative input tokens) and a visual progress bar in the session UI. Issues #114 and #115 build on this to add automatic compaction and configuration UI.

## Research: Context Compaction in AI Coding Assistants

### Claude Code
- Triggers automatic compaction when conversation approaches context limit (~95% of window).
- Compaction creates a summary of the conversation so far, replaces older messages with the summary, and continues.
- The summary preserves: current task context, files being worked on, key decisions made, and pending actions.
- Users see a "[compact] Conversation compacted" message in the chat.
- Can also be triggered manually with `/compact`.
- Uses the same model to generate the summary.

### Cursor
- Uses a "long context" approach: prioritizes recent messages and relevant code context.
- Older messages are silently dropped rather than summarized.
- Relies heavily on retrieval (codebase indexing) rather than keeping everything in context.
- Shows no explicit context usage indicator to the user.

### Aider
- Uses a "chat history summarization" approach.
- When context gets too large, older messages are summarized into a condensed form.
- Keeps a "repository map" (tree-sitter based outline of the codebase) that is always included.
- The summary focuses on what was done and what decisions were made.
- Configurable via `--map-tokens` to control how much space the repo map uses.

### Continue.dev
- Uses a sliding window approach: keeps the most recent N messages.
- Older messages are simply dropped.
- Supports "context providers" that inject relevant code/docs into each request.
- No summarization -- relies on the context providers to re-inject needed context.

### Summary of Strategies

| Strategy | Used By | Pros | Cons |
|----------|---------|------|------|
| Summarization | Claude Code, Aider | Preserves key decisions and context | Costs an extra LLM call, may lose details |
| Sliding window (drop old) | Continue.dev, Cursor | Simple, fast, no extra cost | Loses important early context |
| Retrieval-augmented | Cursor, Continue.dev | Only includes relevant context | Requires indexing infrastructure |

**Recommendation for Codehive:** Use summarization (like Claude Code / Aider) for compaction. This preserves the most context. The compaction engine will be implemented in issue #114.

## Scope (this issue)

1. Model context window size lookup table (backend)
2. Per-API-call tracking of cumulative input tokens vs context window (backend)
3. New API endpoint: `GET /api/sessions/{id}/context` returning current usage and limit
4. Context usage progress bar in the session header (frontend)
5. Real-time updates via existing WebSocket/event infrastructure

## Out of Scope (tracked separately)

- Automatic compaction engine: issue #114
- Compaction configuration UI: issue #115

## Dependencies

- None. Builds on existing UsageRecord infrastructure and session WebSocket events.

## User Stories

### Story: Developer monitors context usage during a coding session
1. User opens a session at `/projects/{id}/sessions/{sid}`
2. Below the session header (next to the engine/model badge), user sees a horizontal progress bar
3. The progress bar shows a thin colored bar: green when usage is under 50%, yellow between 50-80%, red above 80%
4. User hovers over the progress bar and sees a tooltip: "32,450 / 200,000 tokens (16%)"
5. User sends a message; the assistant responds
6. The progress bar updates after the response: the bar visibly grows and the tooltip shows updated numbers
7. As the session progresses, the bar color transitions from green to yellow to red

### Story: Developer sees context usage for CLI-based engines
1. User opens a session running on Claude Code engine
2. The progress bar still appears, but shows a label "estimated" since CLI engines do not report exact token counts
3. For CLI engines, the progress bar shows usage based on accumulated UsageRecord data (if available) or "N/A" if no usage data exists

## E2E Test Scenarios

### Scenario: Context progress bar appears and updates
- Preconditions: A session exists with engine "zai" and at least one exchange (message + response)
- Steps:
  1. Navigate to the session page
  2. Observe the context progress bar in the session header area
- Assertions:
  - A progress bar element with `data-testid="context-progress-bar"` is visible
  - The bar has a non-zero width (indicating some context is used)
  - Hovering shows a tooltip with format "X / Y tokens (Z%)"

### Scenario: Progress bar color changes based on usage level
- Preconditions: A session with known context usage at different levels
- Steps:
  1. Mock context usage at 30% -- verify bar is green
  2. Mock context usage at 65% -- verify bar is yellow
  3. Mock context usage at 90% -- verify bar is red
- Assertions:
  - Green class applied when under 50%
  - Yellow class applied between 50-80%
  - Red class applied above 80%

## Acceptance Criteria

- [ ] `MODEL_CONTEXT_WINDOWS` dict exists in `backend/codehive/core/usage.py` with context window sizes for all models already in `MODEL_PRICES` (Claude Sonnet 4: 200K, Claude Opus 4: 200K, Claude Haiku 3: 200K, codex-mini: 200K as default)
- [ ] `GET /api/sessions/{session_id}/context` returns JSON: `{ "used_tokens": int, "context_window": int, "usage_percent": float, "model": str }`
- [ ] `used_tokens` is computed by summing `input_tokens` from the most recent `UsageRecord` for that session (representing the last API call's input, which includes all prior conversation)
- [ ] Frontend shows a progress bar component in the session header with `data-testid="context-progress-bar"`
- [ ] Progress bar has color coding: green (<50%), yellow (50-80%), red (>80%) via CSS classes
- [ ] Tooltip on hover shows "X / Y tokens (Z%)" format
- [ ] Progress bar updates when new usage data arrives (via polling or WebSocket event)
- [ ] `cd backend && uv run pytest tests/ -v` passes with at least 2 new tests (context window lookup, context endpoint)
- [ ] `cd web && npx vitest run` passes with at least 2 new tests (progress bar rendering, color coding)
- [ ] `cd backend && uv run ruff check` is clean
- [ ] `cd web && npx tsc --noEmit` is clean

## Test Scenarios

### Unit: Model context window lookup
- Verify `MODEL_CONTEXT_WINDOWS["claude-sonnet-4-20250514"]` returns 200000
- Verify unknown model returns a default value (200000)
- Verify `get_context_usage(session_id)` returns correct percentage

### Unit: Context usage API endpoint
- Create a session and a UsageRecord with input_tokens=50000
- Call `GET /api/sessions/{id}/context`
- Verify response contains `used_tokens=50000`, correct `context_window`, and `usage_percent`

### Unit: Frontend progress bar
- Render `ContextProgressBar` with usage at 30% -- verify green color class
- Render with usage at 65% -- verify yellow color class
- Render with usage at 90% -- verify red color class
- Render with usage at 0% -- verify bar width is minimal
- Verify tooltip text format

## Implementation Notes

- The `used_tokens` value should come from the most recent `UsageRecord.input_tokens` for the session. In the Anthropic API, `input_tokens` in the response usage represents the total tokens sent (all messages + system prompt), so the last request's `input_tokens` represents current context utilization.
- For OpenAI Responses API (CodexEngine), the same applies: `usage.input_tokens` reflects total input for that request.
- For CLI engines (ClaudeCodeEngine, CodexCLIEngine), no UsageRecords are created by the engine, so the endpoint should return `used_tokens: 0` with a flag `estimated: true`.
- The frontend component should be placed in `web/src/components/session/ContextProgressBar.tsx`.
- Use the existing `fetchSessionUsage` pattern from `web/src/api/usage.ts` as reference for the new API call.

## Log

### [SWE] 2026-03-18 21:00

- Implemented `MODEL_CONTEXT_WINDOWS` lookup table in `backend/codehive/core/usage.py` with context window sizes for all models in `MODEL_PRICES`
- Added `get_context_window(model)` function with prefix-matching and default fallback (200K)
- Added `get_context_usage(db, session_id)` async function that looks up most recent UsageRecord input_tokens and computes usage percentage
- Added `GET /api/sessions/{session_id}/context` endpoint returning `{ used_tokens, context_window, usage_percent, model, estimated }` in `backend/codehive/api/routes/usage.py`
- Created `web/src/components/ContextProgressBar.tsx` with:
  - Pure `ContextProgressBarView` component (exported for testing)
  - Connected `ContextProgressBar` component with API fetching and WebSocket event refresh
  - Color coding: green (<50%), yellow (50-80%), red (>=80%)
  - Tooltip showing "X / Y tokens (Z%)" with optional "(estimated)" label
  - `data-testid="context-progress-bar"` for e2e testing
- Added `fetchSessionContext` and `ContextUsage` type to `web/src/api/usage.ts`
- Added CSS styles in `web/src/index.css` using Tailwind `@layer components`
- Integrated progress bar into `web/src/pages/SessionPage.tsx` in session header
- Added `useWebSocketSafe()` hook to `web/src/context/WebSocketContext.tsx` for safe usage outside provider
- Updated 3 test file mocks (SessionPage, SessionSidebar, SessionPageModeApprovals) to include `useWebSocketSafe`

Files modified:
- `backend/codehive/core/usage.py` -- MODEL_CONTEXT_WINDOWS, get_context_window, get_context_usage
- `backend/codehive/api/routes/usage.py` -- ContextUsageResponse schema, GET /context endpoint
- `web/src/components/ContextProgressBar.tsx` -- new component
- `web/src/api/usage.ts` -- fetchSessionContext, ContextUsage type
- `web/src/pages/SessionPage.tsx` -- integrated ContextProgressBar
- `web/src/index.css` -- progress bar CSS styles
- `web/src/context/WebSocketContext.tsx` -- useWebSocketSafe hook
- `web/src/test/SessionPage.test.tsx` -- added useWebSocketSafe mock
- `web/src/test/SessionSidebar.test.tsx` -- added useWebSocketSafe mock
- `web/src/test/SessionPageModeApprovals.test.tsx` -- added useWebSocketSafe mock

Tests added:
- Backend: 15 new tests in `test_usage.py`:
  - 8 context window lookup tests (TestContextWindowLookup)
  - 4 context usage function tests (TestContextUsageFunction)
  - 3 context API endpoint tests (TestContextUsageAPI)
- Frontend: 9 new tests in `ContextProgressBar.test.tsx`:
  - Green/yellow/red color coding at various percentages
  - Boundary tests (0%, 50%, 80%, >100%)
  - Tooltip format verification
  - Estimated label presence/absence
- E2E: 2 new tests in `context-progress-bar.spec.ts`:
  - Context API returns valid data for a session
  - Context endpoint returns correct structure with 200K window

Build results:
- Backend: 31 usage tests pass (15 new), 1870 total pass (excluding pre-existing failures in test_models.py and test_ci_pipeline.py)
- Frontend: 623 vitest tests pass (108 test files), all green
- Ruff check: clean
- Ruff format: clean
- tsc --noEmit: clean
- E2E: 2/2 new tests pass, 6/6 total context+usage tests pass

Screenshots:
- `/tmp/e2e-context-progress-bar.png` -- session page with green progress bar visible in header

Known limitations:
- Component placed in `web/src/components/ContextProgressBar.tsx` (not `session/` subdirectory as suggested in implementation notes, since no such directory exists in the codebase)
- For sessions with no usage data, the progress bar shows as a thin green sliver (0.5% minimum width) -- disappears if API returns error

### [QA] 2026-03-18 21:17

**Tests:**
- Backend: 1870 passed, 7 failed (pre-existing failures in test_ci_pipeline.py -- confirmed same on main branch), 3 skipped. All 15 new usage tests pass (8 context window lookup, 4 context usage function, 3 context API endpoint).
- Frontend: 623 passed (108 test files). All 10 new ContextProgressBar tests pass.
- E2E: 2/2 context-progress-bar.spec.ts tests pass. 1 additional QA visual verification test passed.
- Ruff check: clean (All checks passed!)
- Ruff format: clean (248 files already formatted)
- tsc --noEmit: clean

**Acceptance Criteria:**
- [x] `MODEL_CONTEXT_WINDOWS` dict exists in `backend/codehive/core/usage.py` with correct models: PASS -- all models from MODEL_PRICES present plus codex-mini variants, all 200K
- [x] `GET /api/sessions/{session_id}/context` returns correct JSON: PASS -- verified via curl and e2e tests, returns `{ used_tokens, context_window, usage_percent, model, estimated }`
- [x] `used_tokens` computed from most recent UsageRecord's input_tokens: PASS -- verified in backend test `test_context_usage_with_records` and endpoint test `test_get_session_context`
- [x] Frontend shows progress bar with `data-testid="context-progress-bar"`: PASS -- confirmed via Playwright, visible in session header
- [x] Color coding green/yellow/red at correct thresholds: PASS -- unit tests verify green (<50%), yellow (50-80%), red (>=80%). Boundary tests at exactly 50% (yellow) and 80% (red) pass.
- [x] Tooltip shows "X / Y tokens (Z%)": PASS -- e2e test confirmed tooltip "0 / 200,000 tokens (0%)" at 0% usage. Unit test verifies "32,450 / 200,000 tokens (16%)" format.
- [x] Progress bar updates via WebSocket events: PASS -- code uses `useWebSocketSafe()` hook with `ws.onEvent(handler)` to refresh on any event
- [x] Backend tests: 15 new tests pass (exceeds minimum 2): PASS
- [x] Frontend tests: 10 new tests pass (exceeds minimum 2): PASS
- [x] `cd backend && uv run ruff check` clean: PASS
- [x] `cd web && npx tsc --noEmit` clean: PASS

**Visual Verification:**
- Screenshot `/tmp/qa-113-0pct.png`: Session page with dark sidebar, session header showing "qa-vis-sess idle" and "execution" badge. Progress bar visible as a thin grey bar with green sliver (0.5% width) to the left of the execution badge. Tooltip confirmed via automated test.
- Screenshot `/tmp/e2e-context-progress-bar.png` (SWE's): Same layout, progress bar visible in header area.

**Specific Concerns Investigated:**
1. Progress bar at 0% usage: CONFIRMED VISIBLE -- shows as a thin bar with 0.5% green fill. Tooltip shows "0 / 200,000 tokens (0%)". This is acceptable UX.
2. Color coding thresholds: CONFIRMED via unit tests -- green at 30%, yellow at 50% (boundary), yellow at 65%, red at 80% (boundary), red at 90%.

- VERDICT: PASS

### [PM] 2026-03-18 21:27

- Reviewed diff: 13 files changed (362 insertions, 56 deletions)
- Results verified: real data present
  - Backend: 31/31 usage tests pass (15 new context tests), confirmed by running `uv run pytest tests/test_usage.py -v`
  - Frontend: 623/623 vitest tests pass (10 new ContextProgressBar tests), confirmed by running `npx vitest run`
  - Screenshots reviewed: `/tmp/qa-113-0pct.png` shows progress bar in session header as thin green sliver at 0%; `/tmp/e2e-context-progress-bar.png` confirms bar placement
- User story verification:
  - Story 1 (monitor context usage): progress bar visible in header (screenshots), color coding green/yellow/red verified (10 unit tests with boundary cases), tooltip "X / Y tokens (Z%)" format verified (unit test), WebSocket-based refresh implemented (code review)
  - Story 2 (CLI engines): `estimated` flag returned by API, tooltip shows "(estimated)" label when true (unit test)
- Acceptance criteria: all 11 met
  - MODEL_CONTEXT_WINDOWS dict: present with all models, 8 lookup tests pass
  - GET /api/sessions/{id}/context: returns correct JSON, 3 endpoint tests pass
  - used_tokens from most recent UsageRecord: verified by test_context_usage_with_records
  - Frontend data-testid="context-progress-bar": present in component, visible in screenshots
  - Color coding thresholds: green <50%, yellow 50-80%, red >=80% -- all boundary tests pass
  - Tooltip format: verified "32,450 / 200,000 tokens (16%)" in unit test
  - WebSocket updates: useWebSocketSafe() hook with ws.onEvent(handler)
  - Backend tests: 15 new (exceeds 2 minimum)
  - Frontend tests: 10 new (exceeds 2 minimum)
  - Ruff check: clean (QA verified)
  - tsc --noEmit: clean (QA verified)
- Code quality: clean separation of pure view component (ContextProgressBarView) and connected component, proper ARIA attributes for accessibility, safe WebSocket hook pattern
- No scope dropped, no follow-up issues needed
- VERDICT: ACCEPT
