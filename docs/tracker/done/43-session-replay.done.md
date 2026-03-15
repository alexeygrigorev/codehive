# 43: Session Replay

## Description

Implement session replay: the ability to open any completed session and step through its full history of actions chronologically. Shows messages, tool calls, file changes, and terminal output in sequence.

The product spec lists "Session Replay" under Transparency & Observability: "Open any completed session and step through the full history of actions." This builds on the existing `events` table (EventBus from #07), `LogService` (#51), and reuses message rendering components from #16.

## Scope

### Backend

- `backend/codehive/core/replay.py` -- `ReplayService` class that reconstructs an ordered timeline from the events table. Merges events and messages into a unified chronological sequence of "replay steps." Each step has: `index`, `timestamp`, `step_type` (one of `message`, `tool_call_start`, `tool_call_finish`, `file_change`, `task_started`, `task_completed`, `session_status_change`), and `data` (the original event/message payload). Supports pagination (offset/limit).
- `backend/codehive/api/schemas/replay.py` -- Pydantic schemas: `ReplayStep` (index, timestamp, step_type, data), `ReplayResponse` (session_id, session_status, total_steps, steps list).
- `backend/codehive/api/routes/replay.py` -- `GET /api/sessions/{session_id}/replay` endpoint. Returns paginated replay steps. Query params: `limit` (default 50, max 200), `offset` (default 0). Returns 404 if session not found. Only sessions with status `completed` or `failed` are replayable (return 409 otherwise).

### Frontend

- `web/src/pages/ReplayPage.tsx` -- Replay viewer page. Fetches replay data, manages current step index state, renders the current step and controls.
- `web/src/components/ReplayTimeline.tsx` -- Horizontal or vertical timeline bar showing step positions. Clickable to jump to any step. Highlights the current step. Shows step type icons/labels.
- `web/src/components/ReplayStep.tsx` -- Renders a single replay step based on `step_type`. Reuses `MessageBubble` for messages, `ToolCallResult` for tool calls, and renders file changes as simplified diffs. Falls back to a JSON view for unknown step types.
- `web/src/components/ReplayControls.tsx` -- Playback controls: Previous, Next, Play/Pause (auto-advance), speed selector. Shows "Step N of M" indicator.
- Route: `/sessions/:sessionId/replay` added to `App.tsx`.

### Tests

- `backend/tests/test_replay.py` -- Unit tests for `ReplayService` and integration tests for the replay API endpoint.
- `web/src/test/ReplayPage.test.tsx` -- Frontend component tests.
- `web/src/test/ReplayTimeline.test.tsx` -- Timeline component tests.
- `web/src/test/ReplayStep.test.tsx` -- Step rendering tests.
- `web/src/test/ReplayControls.test.tsx` -- Controls component tests.

## Dependencies

- #07 (event bus + events table) -- DONE
- #14 (React app scaffolding) -- DONE
- #16 (session chat panel, MessageBubble, ToolCallResult components) -- DONE
- #51 (persistent logs, LogService) -- DONE

## Acceptance Criteria

- [ ] `ReplayService` in `backend/codehive/core/replay.py` reconstructs a chronological list of replay steps from the events table for a given session
- [ ] Each replay step has `index` (int), `timestamp` (datetime), `step_type` (str), and `data` (dict)
- [ ] `ReplayService` merges events of different types (message.created, tool.call.started, tool.call.finished, file.changed, task.started, task.completed) into a single ordered timeline
- [ ] `GET /api/sessions/{session_id}/replay` returns paginated replay steps with `total_steps` count
- [ ] Replay endpoint returns 404 for nonexistent sessions
- [ ] Replay endpoint returns 409 for sessions that are not `completed` or `failed`
- [ ] `ReplayPage` renders at `/sessions/:sessionId/replay` and displays replay controls and the current step
- [ ] `ReplayTimeline` shows all steps as a navigable bar; clicking a step jumps to it
- [ ] `ReplayControls` supports Previous, Next, Play/Pause, and displays "Step N of M"
- [ ] `ReplayStep` renders `message` steps using `MessageBubble`, `tool_call_start`/`tool_call_finish` steps using `ToolCallResult`, `file_change` steps as diffs, and unknown types as formatted JSON
- [ ] Play/Pause auto-advances through steps at a configurable interval (default 2 seconds)
- [ ] `uv run pytest backend/tests/test_replay.py -v` passes with 8+ tests
- [ ] `cd web && npx vitest run src/test/Replay` passes with 8+ tests (across all Replay*.test.tsx files)

## Test Scenarios

### Unit: ReplayService

- Build replay for a session with mixed event types (message.created, tool.call.started, tool.call.finished, file.changed); verify steps are ordered by timestamp and indexed sequentially
- Build replay for a session with zero events; verify empty steps list and total_steps=0
- Verify pagination: offset=2, limit=2 on a 5-event session returns steps with indices 2-3 and total_steps=5
- Verify step_type mapping: `message.created` events become `message` steps, `tool.call.started` become `tool_call_start` steps, etc.

### Integration: Replay API endpoint

- `GET /api/sessions/{valid_completed_session}/replay` returns 200 with session_id, session_status, total_steps, and a list of ReplayStep objects
- `GET /api/sessions/{nonexistent_id}/replay` returns 404
- `GET /api/sessions/{in_progress_session}/replay` returns 409 with a descriptive error message
- `GET /api/sessions/{session}/replay?limit=2&offset=0` returns exactly 2 steps with correct total_steps
- Verify the response schema matches `ReplayResponse` (session_id, session_status, total_steps, steps)

### Frontend: ReplayPage

- ReplayPage fetches and renders the first step on load
- Clicking Next advances to the next step; clicking Previous goes back
- Previous is disabled on the first step; Next is disabled on the last step
- "Step N of M" indicator updates as the user navigates

### Frontend: ReplayTimeline

- Timeline renders one marker per step
- Clicking a timeline marker updates the current step

### Frontend: ReplayStep

- A step with step_type `message` renders a MessageBubble
- A step with step_type `tool_call_start` or `tool_call_finish` renders a ToolCallResult
- A step with step_type `file_change` renders a diff view
- A step with an unknown step_type renders raw JSON

### Frontend: ReplayControls

- Play button starts auto-advance; Pause button stops it
- Auto-advance stops automatically at the last step

## Out of Scope

- Filtering replay by step type (can be added later)
- Exporting replay data (the existing `/logs/export` endpoint covers raw export)
- Replay for sessions still in progress (live tail is a separate feature)
- Keyboard shortcuts for replay navigation (enhancement for a follow-up)

## Log

### [SWE] 2026-03-15 12:45
- Implemented full session replay feature (backend + frontend)
- Backend:
  - `ReplayService` in `core/replay.py` reconstructs chronological timeline from events table with step_type mapping and pagination
  - Pydantic schemas in `api/schemas/replay.py` (ReplayStep, ReplayResponse)
  - `GET /api/sessions/{id}/replay` endpoint in `api/routes/replay.py` with 404/409 handling
  - Registered replay_router in `api/app.py`
- Frontend:
  - `ReplayPage` at `/sessions/:sessionId/replay` with fetch, navigation, loading/error states
  - `ReplayTimeline` with clickable step markers and current-step highlighting
  - `ReplayControls` with Previous/Next/Play/Pause and "Step N of M" indicator
  - `ReplayStep` renders message steps via MessageBubble, tool calls via ToolCallResult, file changes as diffs, unknown types as JSON
  - API client in `api/replay.ts`
  - Route added to `App.tsx`
- Files modified: backend/codehive/core/replay.py, backend/codehive/api/schemas/replay.py, backend/codehive/api/routes/replay.py, backend/codehive/api/app.py, web/src/api/replay.ts, web/src/components/ReplayStep.tsx, web/src/components/ReplayTimeline.tsx, web/src/components/ReplayControls.tsx, web/src/pages/ReplayPage.tsx, web/src/App.tsx
- Files created for tests: backend/tests/test_replay.py, web/src/test/ReplayPage.test.tsx, web/src/test/ReplayTimeline.test.tsx, web/src/test/ReplayStep.test.tsx, web/src/test/ReplayControls.test.tsx
- Tests added: 12 backend (7 unit + 5 integration), 21 frontend (6 ReplayPage + 4 ReplayTimeline + 5 ReplayStep + 6 ReplayControls)
- Build results: 12 backend tests pass, 21 frontend tests pass, ruff clean
- Known limitations: none

### [QA] 2026-03-15 13:00
- Backend tests: 12 passed, 0 failed (7 unit + 5 integration)
- Frontend tests: 21 passed, 0 failed (6 ReplayPage + 4 ReplayTimeline + 5 ReplayStep + 6 ReplayControls)
- Full backend suite: 977 passed, 0 failed
- Ruff check: clean
- Ruff format: clean
- Frontend build (`npm run build`): FAILS -- TypeScript errors in `web/src/components/ReplayStep.tsx` lines 47 and 53
  - `step.data.action` and `step.data.diff` are type `unknown` (from `Record<string, unknown>`) and cannot be used as ReactNode in JSX conditional expressions
  - Error: TS2322: Type 'unknown' is not assignable to type 'ReactNode'
- Acceptance criteria:
  1. ReplayService reconstructs chronological list of replay steps: PASS
  2. Each replay step has index, timestamp, step_type, data: PASS
  3. ReplayService merges different event types into ordered timeline: PASS
  4. GET /api/sessions/{id}/replay returns paginated steps with total_steps: PASS
  5. Replay endpoint returns 404 for nonexistent sessions: PASS
  6. Replay endpoint returns 409 for non-completed/failed sessions: PASS
  7. ReplayPage renders at /sessions/:sessionId/replay with controls and current step: PASS
  8. ReplayTimeline shows navigable bar, clicking jumps to step: PASS
  9. ReplayControls supports Previous/Next/Play/Pause and "Step N of M": PASS
  10. ReplayStep renders message via MessageBubble, tool calls via ToolCallResult, file changes as diffs, unknown as JSON: PASS
  11. Play/Pause auto-advances at configurable interval (default 2s): PASS
  12. Backend pytest passes with 8+ tests: PASS (12 tests)
  13. Frontend vitest passes with 8+ tests: PASS (21 tests)
- VERDICT: FAIL
- Issues:
  1. TypeScript build failure in `web/src/components/ReplayStep.tsx` (lines 47, 53): `step.data.action` and `step.data.diff` are `unknown` and cannot be rendered as ReactNode. Fix: cast explicitly before using in JSX, e.g. change `{step.data.action && (` to `{typeof step.data.action === "string" && (` or use `{String(step.data.action)}` inside the span. Same for `step.data.diff`.

### [SWE] 2026-03-15 13:10
- Fixed TypeScript build failure from tester feedback
- Changed `{step.data.action && (` to `{typeof step.data.action === "string" && (` on line 47
- Changed `{step.data.diff && (` to `{typeof step.data.diff === "string" && (` on line 53
- These type guards narrow `unknown` to `string`, satisfying TypeScript's ReactNode constraint
- Files modified: web/src/components/ReplayStep.tsx
- Build results: `npm run build` succeeds, 21 frontend tests pass, 12 backend tests pass

### [QA] 2026-03-15 13:15
- Backend tests (`uv run pytest tests/test_replay.py -v`): 12 passed, 0 failed (7 unit + 5 integration)
- Frontend tests (`npx vitest run`): 281 passed, 0 failed (58 test files, includes 21 Replay tests)
- Frontend build (`npm run build`): SUCCESS (tsc + vite, no errors)
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. ReplayService reconstructs chronological list of replay steps: PASS
  2. Each replay step has index, timestamp, step_type, data: PASS
  3. ReplayService merges different event types into ordered timeline: PASS
  4. GET /api/sessions/{id}/replay returns paginated steps with total_steps: PASS
  5. Replay endpoint returns 404 for nonexistent sessions: PASS
  6. Replay endpoint returns 409 for non-completed/failed sessions: PASS
  7. ReplayPage renders at /sessions/:sessionId/replay with controls and current step: PASS
  8. ReplayTimeline shows navigable bar, clicking jumps to step: PASS
  9. ReplayControls supports Previous/Next/Play/Pause and "Step N of M": PASS
  10. ReplayStep renders message via MessageBubble, tool calls via ToolCallResult, file changes as diffs, unknown as JSON: PASS
  11. Play/Pause auto-advances at configurable interval (default 2s): PASS
  12. Backend pytest passes with 8+ tests: PASS (12 tests)
  13. Frontend vitest passes with 8+ tests: PASS (21 tests)
- Previous failure (TypeScript build error in ReplayStep.tsx): FIXED -- typeof guards on lines 47 and 53 correctly narrow `unknown` to `string`
- VERDICT: PASS

### [PM] 2026-03-15 13:30
- Reviewed diff: 15 files changed (3 backend new, 1 backend modified, 6 frontend new, 5 frontend test new)
- Results verified: real data present -- backend 12 tests pass, frontend 281 tests pass (21 Replay-specific), build clean, ruff clean
- Acceptance criteria: all 13 met
  1. ReplayService reconstructs chronological timeline from events table: MET
  2. Each replay step has index (int), timestamp (datetime), step_type (str), data (dict): MET
  3. ReplayService merges different event types into single ordered timeline: MET
  4. GET /api/sessions/{id}/replay returns paginated steps with total_steps: MET
  5. Replay endpoint returns 404 for nonexistent sessions: MET
  6. Replay endpoint returns 409 for non-completed/failed sessions: MET
  7. ReplayPage renders at /sessions/:sessionId/replay with controls and current step: MET
  8. ReplayTimeline shows navigable bar, clicking jumps to step: MET
  9. ReplayControls supports Previous/Next/Play/Pause and "Step N of M": MET
  10. ReplayStep renders message via MessageBubble, tool calls via ToolCallResult, file changes as diffs, unknown as JSON: MET
  11. Play/Pause auto-advances at configurable interval (default 2s): MET
  12. Backend pytest passes with 8+ tests: MET (12 tests)
  13. Frontend vitest passes with 8+ tests: MET (21 tests)
- Code quality: clean, follows existing project patterns (service class + router + Pydantic schemas on backend; component composition with typed props on frontend), proper TypeScript type guards after fix round
- Follow-up issues created: none needed
- VERDICT: ACCEPT
