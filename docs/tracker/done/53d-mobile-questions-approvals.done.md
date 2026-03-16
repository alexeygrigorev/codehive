# 53d: Mobile Questions and Approvals Screens

## Description

Replace the placeholder QuestionsScreen with a fully functional implementation, create a new ApprovalsScreen, add shared card components (QuestionCard, ApprovalCard), wire Approvals into the tab navigator with badge counts, and add tests for all new components and screens.

### Current State

- `QuestionsScreen.tsx` exists as a stub (just renders "Questions" text).
- `mobile/src/api/questions.ts` provides `listQuestions()` and `answerQuestion(id, answer)`.
- `mobile/src/api/approvals.ts` provides `listPendingApprovals()`, `approve(id)`, `reject(id)`.
- No `ApprovalsScreen.tsx` exists yet.
- No `QuestionCard.tsx` or `ApprovalCard.tsx` components exist.
- The tab navigator has 4 tabs: Dashboard, Sessions, Questions, Settings. No Approvals tab.
- Navigation `types.ts` has `QuestionsStackParamList` but no `ApprovalsStackParamList`.
- Backend global questions API returns `QuestionRead` objects with fields: `id`, `session_id`, `question`, `context`, `answered`, `answer`, `created_at`.
- Backend approvals API client calls `/api/approvals` (global), `/api/approvals/{id}/approve`, `/api/approvals/{id}/reject`. Response includes: `id`, `session_id`, `tool_name`, `tool_input`, `description`, `status`, `created_at`.
- Existing tests in `mobile/__tests__/` follow a pattern of mocking API modules and rendering with navigation wrappers.

## Implementation Plan

### 1. QuestionCard component

- `mobile/src/components/QuestionCard.tsx`
- Props: question object, onAnswer callback
- Unanswered state: shows question text, session ID, timestamp, and a TextInput with Submit button
- Answered state: shows question text and the answer, input hidden
- Has `testID` props on key elements for testing

### 2. ApprovalCard component

- `mobile/src/components/ApprovalCard.tsx`
- Props: approval object, onApprove callback, onReject callback
- Shows: action description, tool name, session ID, timestamp
- Two buttons: Approve and Reject
- After action, parent removes the card from the list

### 3. QuestionsScreen (replace stub)

- `mobile/src/screens/QuestionsScreen.tsx`
- Calls `listQuestions()` on mount (filtered to `answered=false` or fetches all and filters client-side)
- Renders FlatList of QuestionCard components
- On answer submission, calls `answerQuestion(id, answer)` then refreshes list or updates local state
- Shows loading indicator while fetching
- Shows empty state ("No pending questions") when list is empty
- Pull-to-refresh support

### 4. ApprovalsScreen

- `mobile/src/screens/ApprovalsScreen.tsx`
- Calls `listPendingApprovals()` on mount
- Renders FlatList of ApprovalCard components
- On approve/reject, calls the respective API function then removes item from list
- Shows loading indicator while fetching
- Shows empty state ("No pending approvals") when list is empty
- Pull-to-refresh support

### 5. Navigation changes

- Add `ApprovalsStackParamList` to `mobile/src/navigation/types.ts`
- Add Approvals tab to `RootNavigator.tsx` (5 tabs: Dashboard, Sessions, Questions, Approvals, Settings)
- Add `RootTabParamList.Approvals` entry

### 6. Badge counts on tabs

- Questions tab shows badge with count of unanswered questions
- Approvals tab shows badge with count of pending approvals
- Counts fetched via API on mount and refreshed periodically or via WebSocket events
- WebSocket: listen for `question.created`, `approval.required` events to increment; `question.answered`, `approval.resolved` to decrement

## Acceptance Criteria

- [ ] `QuestionsScreen` calls `listQuestions()` and renders a FlatList of `QuestionCard` components showing question text, session info, and timestamps
- [ ] Tapping a question reveals a TextInput; submitting calls `answerQuestion(id, answer)` and the card transitions to answered state showing the answer
- [ ] `QuestionsScreen` shows "No pending questions" empty state when the list is empty
- [ ] `QuestionsScreen` supports pull-to-refresh to reload questions
- [ ] `ApprovalsScreen` calls `listPendingApprovals()` and renders a FlatList of `ApprovalCard` components showing action description, tool name, and session info
- [ ] Tapping Approve calls `approve(id)` and removes the card from the list; tapping Reject calls `reject(id)` and removes the card from the list
- [ ] `ApprovalsScreen` shows "No pending approvals" empty state when the list is empty
- [ ] `ApprovalsScreen` supports pull-to-refresh to reload approvals
- [ ] Approvals tab is added to the bottom tab navigator (5 tabs total: Dashboard, Sessions, Questions, Approvals, Settings)
- [ ] `ApprovalsStackParamList` is added to `mobile/src/navigation/types.ts` and `RootTabParamList` includes the Approvals entry
- [ ] Questions tab shows a badge count of pending (unanswered) questions
- [ ] Approvals tab shows a badge count of pending approvals
- [ ] `cd mobile && npx jest` passes with at least 8 new tests covering QuestionCard, ApprovalCard, QuestionsScreen, and ApprovalsScreen

## Test Scenarios

### Unit: QuestionCard (`mobile/__tests__/question-card.test.tsx`)

- Render with unanswered question data; verify question text, session ID, and TextInput are visible
- Type an answer and press Submit; verify onAnswer callback is called with the correct question ID and answer text
- Render with answered question data; verify answer text is displayed and TextInput is not present
- Submit button is disabled or hidden when TextInput is empty

### Unit: ApprovalCard (`mobile/__tests__/approval-card.test.tsx`)

- Render with pending approval data; verify description, tool name, Approve button, and Reject button are visible
- Press Approve; verify onApprove callback is called with the correct approval ID
- Press Reject; verify onReject callback is called with the correct approval ID

### Integration: QuestionsScreen (`mobile/__tests__/questions-screen.test.tsx`)

- Mock `listQuestions()` returning 2 unanswered questions; render QuestionsScreen; verify both question texts appear
- Mock `listQuestions()` returning empty array; verify "No pending questions" text appears
- Mock `listQuestions()` and `answerQuestion()`; answer a question; verify `answerQuestion` was called and the UI updates (card shows answer or is removed from pending)

### Integration: ApprovalsScreen (`mobile/__tests__/approvals-screen.test.tsx`)

- Mock `listPendingApprovals()` returning 2 approvals; render ApprovalsScreen; verify both descriptions appear
- Mock `listPendingApprovals()` returning empty array; verify "No pending approvals" text appears
- Mock `listPendingApprovals()` and `approve()`; tap Approve on one item; verify `approve()` was called and the item is removed from the list

### Navigation: Tab badges (`mobile/__tests__/navigation.test.tsx` or separate)

- Verify the Approvals tab exists in the bottom tab navigator
- Verify badge counts render on Questions and Approvals tabs when counts are non-zero

## Dependencies

- Depends on: #53a (mobile scaffolding, API client, navigation structure) -- must be `.done.md`
- Depends on: #53b (DashboardScreen) -- must be `.done.md` (establishes component and test patterns)
- Uses backend APIs: `GET /api/questions`, `POST /api/questions/{id}/answer`, `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `POST /api/approvals/{id}/reject`

## Notes

- The backend approvals API currently only has per-session endpoints (`/api/sessions/{session_id}/approvals`). The mobile API client calls `/api/approvals` (a global cross-session endpoint). If the global endpoint does not exist yet on the backend, the mobile screens should still be built against the API client as-is. A follow-up backend issue may be needed to add `GET /api/approvals` as a global endpoint. The engineer should note this gap if encountered.
- Existing `SessionWebSocket` connects per-session. For badge counts that span all sessions, consider polling on a timer (e.g., every 30 seconds) as a simpler first pass, with WebSocket-based live updates as a stretch goal or follow-up.

## Log

### [SWE] 2026-03-16 12:00
- Replaced QuestionsScreen stub with full implementation: FlatList of QuestionCard components, loading spinner, empty state, pull-to-refresh, client-side filtering of answered questions, answerQuestion API integration
- Created QuestionCard component: shows question text, session ID, timestamp; unanswered state has TextInput + Submit button (disabled when empty); answered state shows answer text
- Created ApprovalCard component: shows description, tool name, session ID, timestamp; Approve and Reject buttons calling callbacks with approval ID
- Created ApprovalsScreen: FlatList of ApprovalCard components, loading spinner, empty state, pull-to-refresh, approve/reject API integration with card removal
- Added ApprovalsStackParamList to navigation types, added Approvals entry to RootTabParamList (5 tabs total)
- Added Approvals tab to RootNavigator with badge counts on Questions and Approvals tabs (polling every 30 seconds via listQuestions and listPendingApprovals)
- Updated navigation test to verify 5 tabs and badge counts
- Files created: mobile/src/components/QuestionCard.tsx, mobile/src/components/ApprovalCard.tsx, mobile/src/screens/ApprovalsScreen.tsx
- Files modified: mobile/src/screens/QuestionsScreen.tsx (full rewrite), mobile/src/navigation/types.ts, mobile/src/navigation/RootNavigator.tsx, mobile/__tests__/navigation.test.tsx
- Tests added: 4 new test files with 15 new tests (question-card: 4, approval-card: 3, questions-screen: 4, approvals-screen: 4) plus updated navigation test (added badge count test)
- Build results: 75 tests pass, 0 fail; TypeScript clean (npx tsc --noEmit)
- Badge counts use polling (30s interval) as first pass; WebSocket-based live updates deferred per issue notes
- Known limitation: the mobile API client calls global /api/approvals endpoint which may not exist on backend yet (per issue notes)

### [QA] 2026-03-16 12:30
- Tests: 75 passed, 0 failed (21 test suites)
- TypeScript: clean (npx tsc --noEmit passes)
- New tests: 16 (question-card: 4, approval-card: 3, questions-screen: 4, approvals-screen: 4, navigation badge: 1)
- Acceptance criteria:
  1. QuestionsScreen calls listQuestions() and renders FlatList of QuestionCard with question text, session info, timestamps: PASS
  2. Tapping a question reveals TextInput; submitting calls answerQuestion(id, answer) and card transitions to answered state: PASS
  3. QuestionsScreen shows "No pending questions" empty state: PASS
  4. QuestionsScreen supports pull-to-refresh: PASS (RefreshControl wired to fetchQuestions)
  5. ApprovalsScreen calls listPendingApprovals() and renders FlatList of ApprovalCard with description, tool name, session info: PASS
  6. Tapping Approve calls approve(id) and removes card; tapping Reject calls reject(id) and removes card: PASS
  7. ApprovalsScreen shows "No pending approvals" empty state: PASS
  8. ApprovalsScreen supports pull-to-refresh: PASS (RefreshControl wired to fetchApprovals)
  9. Approvals tab added to bottom tab navigator (5 tabs: Dashboard, Sessions, Questions, Approvals, Settings): PASS
  10. ApprovalsStackParamList added to types.ts and RootTabParamList includes Approvals entry: PASS
  11. Questions tab shows badge count of pending (unanswered) questions: PASS
  12. Approvals tab shows badge count of pending approvals: PASS
  13. Tests pass with at least 8 new tests covering QuestionCard, ApprovalCard, QuestionsScreen, ApprovalsScreen: PASS (16 new tests)
- Note: diff includes unrelated changes from issue 55a (backend project_flow router, deleted tracker files). These do not affect this issue but should be separated at commit time.
- VERDICT: PASS

### [PM] 2026-03-16 13:00
- Reviewed diff: 8 files changed in mobile/ (3 new components/screens, 4 new test files, 1 modified navigation test, plus RootNavigator.tsx, types.ts, QuestionsScreen.tsx)
- Results verified: real data present -- 75 tests pass (21 suites), TypeScript clean, 16 new tests confirmed
- Acceptance criteria: all 13 met
  1. QuestionsScreen calls listQuestions(), renders FlatList of QuestionCard with question text, session info, timestamps: MET
  2. TextInput + answerQuestion API integration with state transition: MET
  3. Empty state "No pending questions": MET
  4. Pull-to-refresh on QuestionsScreen: MET
  5. ApprovalsScreen calls listPendingApprovals(), renders FlatList of ApprovalCard: MET
  6. Approve/Reject calls respective API and removes card: MET
  7. Empty state "No pending approvals": MET
  8. Pull-to-refresh on ApprovalsScreen: MET
  9. 5-tab navigator (Dashboard, Sessions, Questions, Approvals, Settings): MET
  10. ApprovalsStackParamList and RootTabParamList.Approvals in types.ts: MET
  11. Questions tab badge count (unanswered questions): MET
  12. Approvals tab badge count (pending approvals): MET
  13. 16 new tests (>= 8 required): MET
- Code quality: clean, follows established patterns (same structure as DashboardScreen/SessionDetailScreen), proper testIDs, useCallback/useEffect hooks, proper typing
- Badge polling at 30s interval is appropriate first-pass per issue notes; WebSocket upgrade is a known follow-up
- Follow-up issues created: none needed
- VERDICT: ACCEPT
