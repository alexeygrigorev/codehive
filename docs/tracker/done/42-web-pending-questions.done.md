# 42: Web Pending Questions UI

## Description
Build the pending questions interface in the web app. Users should see unanswered questions across all sessions, answer them inline, and have answers submitted back via the API. This includes a global questions page (all sessions), a per-session questions panel in the sidebar, and a reusable question card component with an answer form.

## Scope
- `web/src/api/questions.ts` -- API hooks: `fetchAllQuestions(answered?)`, `fetchSessionQuestions(sessionId, answered?)`, `answerQuestion(sessionId, questionId, answer)` using existing `apiClient`; typed `QuestionRead` interface matching backend schema (id, session_id, question, context, answered, answer, created_at)
- `web/src/components/QuestionCard.tsx` -- Reusable component displaying a single pending question: question text, context (if present), session ID, timestamp, answered/unanswered status badge, and an inline answer form (textarea + submit button) for unanswered questions; shows the answer text for already-answered questions
- `web/src/components/sidebar/QuestionsPanel.tsx` -- Per-session pending questions panel for the sidebar; fetches questions via `fetchSessionQuestions(sessionId)`; shows unanswered questions first, then answered; integrates with the sidebar tab system
- `web/src/pages/QuestionsPage.tsx` -- Global pending questions page listing questions across all sessions; fetches via `fetchAllQuestions()`; shows unanswered questions first; each question card links to its session
- Update `web/src/App.tsx` -- Add route `/questions` pointing to `QuestionsPage`
- Update `web/src/components/sidebar/SidebarTabs.tsx` -- Add a "Questions" tab (key: `"questions"`) that renders `QuestionsPanel`

## Dependencies
- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #10 (pending questions API: `GET /api/questions`, `GET /api/sessions/{id}/questions`, `POST /api/sessions/{id}/questions/{qid}/answer`) -- DONE
- Depends on: #17 (session sidebar with tab system) -- DONE
- Depends on: #18 (WebSocket client for real-time event notifications) -- DONE

## Backend API Reference

The following backend endpoints already exist (from #10):

- `GET /api/questions?answered=bool` -- List all questions across sessions (global)
- `GET /api/sessions/{session_id}/questions?answered=bool` -- List questions for a session
- `POST /api/sessions/{session_id}/questions/{question_id}/answer` -- Body: `{"answer": "..."}`, returns updated question; 404 if not found; 409 if already answered

Response schema (`QuestionRead`):
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "question": "string",
  "context": "string | null",
  "answered": false,
  "answer": "string | null",
  "created_at": "iso8601"
}
```

## Acceptance Criteria

- [ ] `cd /home/alexey/git/codehive/web && npx vitest run` passes with 20+ new tests and all existing tests green
- [ ] `web/src/api/questions.ts` exports `QuestionRead` interface with fields: id, session_id, question, context, answered, answer, created_at
- [ ] `web/src/api/questions.ts` exports `fetchAllQuestions(answered?)` that calls `GET /api/questions` with optional `answered` query param
- [ ] `web/src/api/questions.ts` exports `fetchSessionQuestions(sessionId, answered?)` that calls `GET /api/sessions/{sessionId}/questions` with optional `answered` query param
- [ ] `web/src/api/questions.ts` exports `answerQuestion(sessionId, questionId, answer)` that calls `POST /api/sessions/{sessionId}/questions/{questionId}/answer` with `{"answer": "..."}` body
- [ ] `answerQuestion` throws on non-200 response (404, 409, etc.)
- [ ] `QuestionCard` displays the question text, context (when present), relative timestamp, and an answered/unanswered status badge
- [ ] `QuestionCard` for unanswered questions renders an answer form with a textarea and a submit button
- [ ] `QuestionCard` submit button is disabled while the textarea is empty
- [ ] `QuestionCard` calls `answerQuestion` on form submit and shows the answered state after success
- [ ] `QuestionCard` displays an error message if `answerQuestion` fails (e.g., 409 already answered)
- [ ] `QuestionCard` for already-answered questions displays the answer text and does not show the input form
- [ ] `QuestionsPage` is routed at `/questions` in `App.tsx`
- [ ] `QuestionsPage` fetches all questions via `fetchAllQuestions()` and renders a `QuestionCard` for each
- [ ] `QuestionsPage` shows unanswered questions before answered questions
- [ ] `QuestionsPage` handles loading, empty, and error states
- [ ] `QuestionsPanel` fetches per-session questions via `fetchSessionQuestions(sessionId)` and renders `QuestionCard` for each
- [ ] `QuestionsPanel` handles loading, empty, and error states
- [ ] `SidebarTabs` includes a "Questions" tab that renders `QuestionsPanel` when active
- [ ] Answering a question on `QuestionsPage` updates the card in-place to show the answered state (no full page reload required)
- [ ] TypeScript compilation passes (`tsc --noEmit`)
- [ ] Vite build succeeds (`npx vite build`)

## Test Scenarios

### Unit: API hooks (`questions.test.ts`)
- `fetchAllQuestions()` calls `GET /api/questions` and returns `QuestionRead[]`
- `fetchAllQuestions(false)` calls `GET /api/questions?answered=false`
- `fetchAllQuestions()` throws on non-200 response
- `fetchSessionQuestions(sessionId)` calls `GET /api/sessions/{sessionId}/questions` and returns `QuestionRead[]`
- `fetchSessionQuestions(sessionId, false)` includes `?answered=false` query param
- `fetchSessionQuestions` throws on non-200 response
- `answerQuestion(sessionId, questionId, answer)` calls `POST /api/sessions/{sessionId}/questions/{questionId}/answer` with correct body and returns `QuestionRead`
- `answerQuestion` throws on 409 (already answered) or 404 response

### Unit: QuestionCard (`QuestionCard.test.tsx`)
- Renders question text and context
- Renders relative timestamp (e.g., "2 minutes ago" or formatted date)
- Shows "Unanswered" badge for unanswered questions
- Shows "Answered" badge for answered questions
- Renders textarea and submit button for unanswered questions
- Does not render textarea or submit button for answered questions
- Displays the answer text for answered questions
- Submit button is disabled when textarea is empty
- Submitting an answer calls `answerQuestion` with correct arguments
- After successful answer submission, card shows answered state with answer text
- When `answerQuestion` rejects, an error message is displayed

### Unit: QuestionsPage (`QuestionsPage.test.tsx`)
- Renders a heading (e.g., "Pending Questions")
- Fetches questions via `fetchAllQuestions` and renders QuestionCard for each
- Unanswered questions appear before answered questions in the list
- Shows loading state while fetching
- Shows empty state when no questions exist
- Shows error state when fetch fails

### Unit: QuestionsPanel (`QuestionsPanel.test.tsx`)
- Fetches questions via `fetchSessionQuestions(sessionId)` and renders QuestionCard for each
- Shows loading state while fetching
- Shows empty state when no questions exist (e.g., "No pending questions")
- Shows error state when fetch fails

### Integration: SidebarTabs with Questions tab
- SidebarTabs renders a "Questions" tab
- Clicking the "Questions" tab renders QuestionsPanel

### Integration: App routing
- Navigating to `/questions` renders QuestionsPage

## Technical Notes
- Follow existing patterns: `apiClient.get`/`apiClient.post` from `web/src/api/client.ts`, `useEffect` with cancellation flags, consistent loading/empty/error state handling
- SidebarTabs currently has 4 tabs (ToDo, Changed Files, Timeline, Sub-agents); add "Questions" as a 5th tab
- The `QuestionCard` component should be self-contained: it manages its own form state and submission, calling the API directly
- Use `vi.mock` / `vi.fn` for API mocking in tests, consistent with existing test files
- The `QuestionsPage` can optionally show which session each question belongs to (session_id), since it shows questions across all sessions

## Log

### [SWE] 2026-03-15 12:28
- Implemented all components for pending questions UI
- Created `web/src/api/questions.ts` with QuestionRead interface and three API functions: fetchAllQuestions, fetchSessionQuestions, answerQuestion
- Created `web/src/components/QuestionCard.tsx` -- self-contained card with inline answer form, status badges, relative timestamps, error handling
- Created `web/src/components/sidebar/QuestionsPanel.tsx` -- per-session questions panel with loading/empty/error states, unanswered-first sorting
- Created `web/src/pages/QuestionsPage.tsx` -- global questions page with loading/empty/error states, unanswered-first sorting, shows session_id per card
- Updated `web/src/App.tsx` -- added /questions route
- Updated `web/src/components/sidebar/SidebarTabs.tsx` -- added "Questions" as 5th tab rendering QuestionsPanel
- Updated `web/src/test/SidebarTabs.test.tsx` -- added QuestionsPanel mock, updated tab count test, added 2 integration tests for Questions tab
- Updated `web/src/test/App.test.tsx` -- added QuestionsPage route and /questions routing test
- Files created: web/src/api/questions.ts, web/src/components/QuestionCard.tsx, web/src/components/sidebar/QuestionsPanel.tsx, web/src/pages/QuestionsPage.tsx, web/src/test/questions.test.ts, web/src/test/QuestionCard.test.tsx, web/src/test/QuestionsPage.test.tsx, web/src/test/QuestionsPanel.test.tsx
- Files modified: web/src/App.tsx, web/src/components/sidebar/SidebarTabs.tsx, web/src/test/SidebarTabs.test.tsx, web/src/test/App.test.tsx
- Tests added: 30 new tests (9 API, 11 QuestionCard, 6 QuestionsPage, 4 QuestionsPanel, plus updated SidebarTabs and App routing tests)
- Build results: 222 tests pass, 0 fail; tsc --noEmit clean; vite build succeeds
- Known limitations: none

### [QA] 2026-03-15 12:35
- Tests: 222 passed, 0 failed (30 new question-related tests)
- TypeScript: tsc --noEmit clean
- Vite build: succeeds
- Acceptance criteria:
  - AC1 (20+ new tests, all green): PASS -- 30 new, 222 total
  - AC2 (QuestionRead interface): PASS
  - AC3 (fetchAllQuestions): PASS
  - AC4 (fetchSessionQuestions): PASS
  - AC5 (answerQuestion): PASS
  - AC6 (answerQuestion throws on non-200): PASS
  - AC7 (QuestionCard displays text, context, timestamp, badge): PASS
  - AC8 (QuestionCard answer form for unanswered): PASS
  - AC9 (submit button disabled while empty): PASS
  - AC10 (QuestionCard calls answerQuestion, shows answered state): PASS
  - AC11 (QuestionCard error on failure): PASS
  - AC12 (answered card shows answer, no form): PASS
  - AC13 (QuestionsPage at /questions): PASS
  - AC14 (QuestionsPage fetches and renders cards): PASS
  - AC15 (unanswered before answered): PASS
  - AC16 (QuestionsPage loading/empty/error): PASS
  - AC17 (QuestionsPanel fetches per-session): PASS
  - AC18 (QuestionsPanel loading/empty/error): PASS
  - AC19 (SidebarTabs Questions tab): PASS
  - AC20 (in-place update on answer): PASS
  - AC21 (tsc --noEmit): PASS
  - AC22 (vite build): PASS
- VERDICT: PASS

### [PM] 2026-03-15 12:45
- Reviewed diff: 12 files changed (8 new, 4 modified in web/; backend changes are unrelated to this issue)
- Results verified: real data present -- 222 tests pass, tsc --noEmit clean, vite build succeeds (independently verified)
- Code review:
  - `web/src/api/questions.ts`: Clean API layer, correct endpoint URLs, proper error handling with throws on non-200, typed QuestionRead matches backend schema exactly
  - `web/src/components/QuestionCard.tsx`: Self-contained component with local state management, inline answer form, relative timestamp formatting, status badges, error display -- well structured
  - `web/src/components/sidebar/QuestionsPanel.tsx`: Follows existing panel patterns (useEffect with cancellation flag), loading/empty/error states, unanswered-first sorting, passes sessionId correctly
  - `web/src/pages/QuestionsPage.tsx`: Same pattern as panel but for global view, shows session_id per card via showSessionId prop, proper state handling
  - `web/src/App.tsx`: /questions route added correctly
  - `web/src/components/sidebar/SidebarTabs.tsx`: Questions added as 5th tab, TabKey union type updated, rendering conditional added
  - Tests are meaningful: 9 API tests cover all endpoints + error cases, 11 QuestionCard tests cover rendering/interaction/error/state transitions, 6 QuestionsPage tests cover fetch/sort/states, 4 QuestionsPanel tests cover fetch/states, plus SidebarTabs and App routing integration tests
- Acceptance criteria: all 22 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
