# 76: Mobile New Project Flow

## Description

Add the guided project creation wizard to the mobile app (similar to web `NewProjectPage`). This is a multi-step flow: the user picks a flow type, answers questions in a chat-like interface, reviews the generated project brief, and finalizes to create the project. The mobile version consumes the same three backend endpoints from #55a.

## Scope

**In scope:**
- API client module `mobile/src/api/projectFlow.ts` wrapping the three backend endpoints (`start`, `respond`, `finalize`)
- TypeScript interfaces matching backend Pydantic schemas (FlowQuestion, FlowAnswer, ProjectBrief, SuggestedSession, etc.)
- `NewProjectScreen` (`mobile/src/screens/NewProjectScreen.tsx`) -- flow type selection with 4 cards (Brainstorm, Guided Interview, From Notes, From Repository)
- `FlowChatScreen` (`mobile/src/screens/FlowChatScreen.tsx`) -- renders questions as form fields, collects answers, submits via `respondToFlow`, handles next_questions or brief transitions
- `BriefReviewScreen` (`mobile/src/screens/BriefReviewScreen.tsx`) -- displays the generated brief with editable name/description, shows tech stack, architecture, open decisions, suggested sessions, and a "Create Project" button that calls `finalizeFlow`
- Navigation: add `NewProject`, `FlowChat`, and `BriefReview` screens to `DashboardStackParamList` and `DashboardStackNavigator`
- "New Project" button on `DashboardScreen` (e.g., in the header or as a FAB)
- After successful finalization, navigate to `ProjectSessions` for the newly created project
- Loading, error, and empty states for all steps
- Initial input field for "From Notes" and "From Repository" flow types

**Out of scope:**
- Real LLM-generated questions (backend uses deterministic stubs)
- WebSocket streaming of flow events (request-response only)
- Flow persistence across app restarts (in-memory state is acceptable)

## Implementation Plan

### 1. API client module
- `mobile/src/api/projectFlow.ts`
- `startFlow(body)`, `respondToFlow(flowId, answers)`, `finalizeFlow(flowId)` -- same contract as `web/src/api/projectFlow.ts`
- Uses existing `apiClient` from `mobile/src/api/client.ts`

### 2. Flow type selection screen
- `mobile/src/screens/NewProjectScreen.tsx`
- Four touchable cards in a ScrollView: Brainstorm, Guided Interview, From Notes, From Repository
- Each card shows title and description
- For "From Notes" and "From Repository", show a TextInput for initial input before proceeding
- Tapping a card (or "Continue" for input-required types) calls `startFlow()` and navigates to `FlowChat`

### 3. Flow chat screen
- `mobile/src/screens/FlowChatScreen.tsx`
- Receives `flowId` and `questions` via navigation params
- Renders one TextInput per question, with category label grouping
- "Submit" button calls `respondToFlow()` with collected answers
- If response has `next_questions`, replace current questions with new batch
- If response has `brief`, navigate to `BriefReview`

### 4. Brief review screen
- `mobile/src/screens/BriefReviewScreen.tsx`
- Receives `flowId` and `brief` via navigation params (or via state)
- Displays: project name (editable TextInput), description (editable TextInput multiline), tech stack, architecture, open decisions list, suggested sessions list
- "Create Project" button calls `finalizeFlow()`
- On success, navigate to `ProjectSessions` with the new project

### 5. Navigation updates
- Add to `DashboardStackParamList`: `NewProject`, `FlowChat`, `BriefReview` routes
- Add screens to `DashboardStackNavigator` in `RootNavigator.tsx`
- Add "New Project" button to `DashboardScreen`

## Acceptance Criteria

- [ ] `mobile/src/api/projectFlow.ts` exports `startFlow`, `respondToFlow`, `finalizeFlow` functions with TypeScript interfaces matching the backend schemas (`FlowQuestion`, `FlowAnswer`, `ProjectBrief`, `SuggestedSession`, `FlowStartResult`, `FlowRespondResult`, `FlowFinalizeResult`, `CreatedSession`)
- [ ] `NewProjectScreen` renders four flow type cards with titles: "Brainstorm", "Guided Interview", "From Notes", "From Repository" -- each with a description
- [ ] Tapping "Brainstorm" or "Guided Interview" calls `startFlow` with the correct `flow_type` (`brainstorm` or `interview`) and navigates to `FlowChatScreen`
- [ ] Tapping "From Notes" or "From Repository" shows a TextInput for initial input; a "Continue" button calls `startFlow` with `flow_type` and `initial_input`
- [ ] `FlowChatScreen` renders one TextInput per question from the `questions` navigation param, with the question text as a label
- [ ] `FlowChatScreen` "Submit" button calls `respondToFlow(flowId, answers)` with `{answers: [{question_id, answer}]}` payload
- [ ] When `respondToFlow` returns `next_questions` (non-null), `FlowChatScreen` replaces the current questions with the new batch
- [ ] When `respondToFlow` returns `brief` (non-null), the app navigates to `BriefReviewScreen` with the brief data
- [ ] `BriefReviewScreen` displays all brief fields: name, description, tech_stack, architecture, open_decisions, suggested_sessions (with name, mission, mode per session)
- [ ] `BriefReviewScreen` allows editing the project name and description via editable TextInput fields
- [ ] Pressing "Create Project" on `BriefReviewScreen` calls `finalizeFlow(flowId)`
- [ ] After successful finalization, the app navigates to `ProjectSessions` with the new `project_id` and project name from the brief
- [ ] Loading indicators (ActivityIndicator) are shown during all API calls (start, respond, finalize)
- [ ] Error messages are displayed when API calls fail (network errors, 4xx/5xx)
- [ ] `DashboardScreen` has a "New Project" button that navigates to `NewProjectScreen`
- [ ] `DashboardStackParamList` in `types.ts` includes `NewProject`, `FlowChat`, and `BriefReview` routes with appropriate params
- [ ] All new screens are registered in `DashboardStackNavigator` in `RootNavigator.tsx`
- [ ] `npx jest` in `mobile/` passes with 15+ new tests across the new files
- [ ] No TypeScript errors: `npx tsc --noEmit` in `mobile/` passes

## Test Scenarios

### Unit: API client (`mobile/__tests__/project-flow-api.test.ts`)
- `startFlow` calls `apiClient.post("/api/project-flow/start", ...)` with correct body and returns parsed response
- `respondToFlow` calls `apiClient.post("/api/project-flow/{flowId}/respond", ...)` with answers array
- `finalizeFlow` calls `apiClient.post("/api/project-flow/{flowId}/finalize")` and returns parsed result
- API functions propagate errors on non-2xx responses

### Unit: NewProjectScreen (`mobile/__tests__/new-project-screen.test.tsx`)
- Renders four flow type cards with expected titles (Brainstorm, Guided Interview, From Notes, From Repository)
- Each card has a description text
- Tapping "Brainstorm" card calls `startFlow` with `flow_type: "brainstorm"`
- Tapping "From Notes" card shows a TextInput and "Continue" button (does not call startFlow immediately)
- "Continue" button is disabled when initial input is empty
- Shows ActivityIndicator while `startFlow` is pending
- Shows error message when `startFlow` rejects

### Unit: FlowChatScreen (`mobile/__tests__/flow-chat-screen.test.tsx`)
- Renders one TextInput per question passed via navigation params
- Displays question text as label above each TextInput
- "Submit" button calls `respondToFlow` with correctly shaped answers payload
- Shows ActivityIndicator during submit
- When response has `next_questions`, re-renders with new question TextInputs
- When response has `brief`, triggers navigation to BriefReview
- Shows error message when `respondToFlow` rejects

### Unit: BriefReviewScreen (`mobile/__tests__/brief-review-screen.test.tsx`)
- Renders project name in an editable TextInput
- Renders project description in an editable multiline TextInput
- Renders tech stack entries as text
- Renders each suggested session with name, mission, and mode
- Renders open decisions list
- Editing name updates the displayed value
- "Create Project" button calls `finalizeFlow` with the flow_id
- Shows ActivityIndicator during finalization
- Shows error message when `finalizeFlow` rejects
- After successful finalization, navigates to ProjectSessions

### Integration: Navigation
- "New Project" button on DashboardScreen navigates to NewProjectScreen
- DashboardStackParamList includes NewProject, FlowChat, and BriefReview routes
- NewProject, FlowChat, and BriefReview screens are registered in DashboardStackNavigator

## Dependencies

- Depends on: #53b (mobile dashboard -- done), #55a (project flow backend -- done)
- Related: #55b (web frontend equivalent -- done, use as reference for UX patterns)

## Log

### [SWE] 2026-03-16 14:00
- Implemented the full mobile new project flow: API client, 3 screens, navigation updates, dashboard button
- API client (`projectFlow.ts`) wraps start/respond/finalize endpoints using axios pattern matching other mobile API modules
- `NewProjectScreen`: 4 flow type cards, input section for From Notes/From Repository, loading/error states
- `FlowChatScreen`: renders questions grouped by category, collects answers, handles next_questions and brief transitions
- `BriefReviewScreen`: editable name/description, displays tech_stack/architecture/open_decisions/suggested_sessions, Create Project button with finalize
- Navigation types updated with NewProject, FlowChat, BriefReview routes
- RootNavigator updated with 3 new screens in DashboardStackNavigator
- DashboardScreen: added "New Project" button in header via setOptions
- Files created:
  - `mobile/src/api/projectFlow.ts`
  - `mobile/src/screens/NewProjectScreen.tsx`
  - `mobile/src/screens/FlowChatScreen.tsx`
  - `mobile/src/screens/BriefReviewScreen.tsx`
  - `mobile/__tests__/project-flow-api.test.ts`
  - `mobile/__tests__/new-project-screen.test.tsx`
  - `mobile/__tests__/flow-chat-screen.test.tsx`
  - `mobile/__tests__/brief-review-screen.test.tsx`
- Files modified:
  - `mobile/src/navigation/types.ts`
  - `mobile/src/navigation/RootNavigator.tsx`
  - `mobile/src/screens/DashboardScreen.tsx`
- Tests added: 32 new tests across 4 test files (7 API, 7 NewProject, 7 FlowChat, 11 BriefReview)
- Build results: 162 tests pass (39 suites), 0 fail, TypeScript clean (tsc --noEmit passes)
- Known limitations: none

### [QA] 2026-03-16 15:30
- Tests: 162 passed, 0 failed (32 new tests across 4 test files)
- TypeScript: `npx tsc --noEmit` clean
- Acceptance criteria:
  1. `projectFlow.ts` exports `startFlow`, `respondToFlow`, `finalizeFlow` with TS interfaces (FlowQuestion, FlowAnswer, ProjectBrief, SuggestedSession, FlowStartResult, FlowRespondResult, FlowFinalizeResult, CreatedSession): PASS
  2. `NewProjectScreen` renders four flow type cards (Brainstorm, Guided Interview, From Notes, From Repository) with descriptions: PASS
  3. Tapping Brainstorm/Guided Interview calls `startFlow` with correct `flow_type` and navigates to FlowChatScreen: PASS
  4. Tapping From Notes/From Repository shows TextInput for initial input; Continue button calls `startFlow` with `flow_type` and `initial_input`: PASS
  5. `FlowChatScreen` renders one TextInput per question with question text as label: PASS
  6. `FlowChatScreen` Submit button calls `respondToFlow(flowId, answers)` with `{answers: [{question_id, answer}]}` payload: PASS
  7. When `respondToFlow` returns `next_questions`, FlowChatScreen replaces current questions with new batch: PASS
  8. When `respondToFlow` returns `brief`, app navigates to BriefReviewScreen with brief data: PASS (code path exercised, navigation verified via code review)
  9. `BriefReviewScreen` displays all brief fields (name, description, tech_stack, architecture, open_decisions, suggested_sessions with name/mission/mode): PASS
  10. `BriefReviewScreen` allows editing project name and description via editable TextInput fields: PASS
  11. Pressing Create Project calls `finalizeFlow(flowId)`: PASS
  12. After successful finalization, navigates to ProjectSessions with project_id and project name: PASS (code review confirms correct navigate call; test exercises the path)
  13. Loading indicators (ActivityIndicator) shown during all API calls (start, respond, finalize): PASS
  14. Error messages displayed when API calls fail: PASS
  15. DashboardScreen has New Project button navigating to NewProjectScreen: PASS
  16. `DashboardStackParamList` includes NewProject, FlowChat, BriefReview routes with appropriate params: PASS
  17. All new screens registered in DashboardStackNavigator in RootNavigator.tsx: PASS
  18. `npx jest` passes with 15+ new tests (32 new tests): PASS
  19. No TypeScript errors (`npx tsc --noEmit` passes): PASS
- Notes: BriefReviewScreen navigation-after-finalize test only verifies finalizeFlow was called, not that navigation.navigate was invoked with correct args. Not blocking since the code is correct and the path is exercised.
- VERDICT: PASS

### [PM] 2026-03-16 16:00
- Reviewed diff: 11 files changed (4 new screens/API, 4 new test files, 3 modified navigation/dashboard files)
- Results verified: real test data present -- 162 tests pass (32 new), TypeScript clean
- Acceptance criteria: all 19 met
  1. API client exports startFlow, respondToFlow, finalizeFlow with all 8 TS interfaces: MET
  2. NewProjectScreen renders 4 flow type cards with titles and descriptions: MET
  3. Brainstorm/Interview tap calls startFlow with correct flow_type and navigates to FlowChat: MET
  4. From Notes/Repository shows TextInput + Continue button with initial_input: MET
  5. FlowChatScreen renders one TextInput per question with label: MET
  6. Submit calls respondToFlow with {answers: [{question_id, answer}]}: MET
  7. next_questions response replaces current questions: MET
  8. brief response navigates to BriefReviewScreen: MET
  9. BriefReviewScreen displays all brief fields (name, description, tech_stack, architecture, open_decisions, suggested_sessions with name/mission/mode): MET
  10. Editable name and description via TextInput: MET
  11. Create Project calls finalizeFlow(flowId): MET
  12. Post-finalize navigates to ProjectSessions with project_id and projectName: MET
  13. ActivityIndicator during all API calls: MET
  14. Error messages on API failures: MET
  15. Dashboard New Project button navigates to NewProjectScreen: MET
  16. DashboardStackParamList includes NewProject, FlowChat, BriefReview with correct params: MET
  17. All 3 new screens registered in DashboardStackNavigator: MET
  18. 32 new tests (exceeds 15+ requirement): MET
  19. TypeScript clean: MET
- Code quality: clean, follows existing project patterns (same apiClient pattern, consistent StyleSheet usage, proper testIDs, proper loading/error state handling)
- Minor note: BriefReviewScreen finalization test verifies finalizeFlow call but not navigation.navigate args -- code is correct, not blocking
- Follow-up issues created: none
- VERDICT: ACCEPT
