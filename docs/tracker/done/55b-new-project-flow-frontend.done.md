# 55b: New Project Flow -- Frontend

## Description

Web UI wizard for guided project creation. User selects a flow type, goes through brainstorm/interview conversation, reviews the generated brief, and finalizes to create the project.

This consumes the three backend endpoints from #55a:
- `POST /api/project-flow/start` -- starts a flow, returns `flow_id`, `session_id`, `first_questions`
- `POST /api/project-flow/{flow_id}/respond` -- sends answers, returns `next_questions` or `brief`
- `POST /api/project-flow/{flow_id}/finalize` -- creates project and sessions, returns `project_id` and `sessions`

## Scope

**In scope:**
- API client module `web/src/api/projectFlow.ts` wrapping the three backend endpoints
- `NewProjectPage` (`web/src/pages/NewProjectPage.tsx`) -- flow type selection (4 cards)
- `FlowChat` component (`web/src/components/project-flow/FlowChat.tsx`) -- chat/form UI for questions and answers
- `BriefReview` component (`web/src/components/project-flow/BriefReview.tsx`) -- editable brief review before finalization
- Route `/projects/new` added to `App.tsx` (protected, inside layout)
- "New Project" button on `DashboardPage`
- Redirect to `/projects/{project_id}` after successful finalization
- Loading, error, and empty states for all steps

**Out of scope:**
- Real LLM-generated questions (backend uses deterministic stubs for now)
- WebSocket streaming of flow events (polling/request-response only)
- Flow persistence across page refreshes (in-memory state is acceptable for MVP)

## Implementation Plan

### 1. API client module
- `web/src/api/projectFlow.ts`
- `startFlow(body: { flow_type, initial_input, workspace_id }): Promise<FlowStartResult>`
- `respondToFlow(flowId: string, answers: FlowAnswer[]): Promise<FlowRespondResult>`
- `finalizeFlow(flowId: string): Promise<FlowFinalizeResult>`
- TypeScript interfaces matching backend Pydantic schemas: `FlowQuestion`, `FlowAnswer`, `ProjectBrief`, `SuggestedSession`, `CreatedSession`, `FlowStartResult`, `FlowRespondResult`, `FlowFinalizeResult`
- Uses existing `apiClient` from `web/src/api/client.ts`

### 2. Flow selection page
- `web/src/pages/NewProjectPage.tsx` -- entry point at `/projects/new`
- Four cards: "Brainstorm", "Guided Interview", "From Notes", "From Repository"
- Each card has a title, description, and visual distinction
- Optional initial input field (required for "From Notes" and "From Repository")
- Clicking a card calls `startFlow()` and transitions to the chat step
- Loading state while the start request is in flight
- Error state if the start request fails

### 3. Interview/brainstorm chat
- `web/src/components/project-flow/FlowChat.tsx`
- Displays questions from the backend as form fields (one text input/textarea per question)
- Groups questions by category label (goals, tech, architecture, constraints, team)
- Submit button sends answers via `respondToFlow()`
- On response: if `next_questions` is non-null, render the next batch; if `brief` is non-null, transition to review step
- Loading state during submit
- Error state if the respond request fails

### 4. Brief review
- `web/src/components/project-flow/BriefReview.tsx`
- Displays: project name (editable input), description (editable textarea), tech stack (read-only or editable), architecture (read-only or editable), open decisions (list), suggested sessions (list with name/mission/mode)
- "Create Project" button calls `finalizeFlow()`
- Loading state during finalization
- Error state if finalization fails

### 5. Navigation and routing
- Add route `<Route path="/projects/new" element={<NewProjectPage />} />` inside the protected layout in `App.tsx` (must be above the `/projects/:projectId` route to avoid matching)
- Add "New Project" button/link on `DashboardPage` that navigates to `/projects/new`
- After successful finalization, `useNavigate()` to `/projects/{project_id}`

## Acceptance Criteria

- [ ] `web/src/api/projectFlow.ts` exports `startFlow`, `respondToFlow`, `finalizeFlow` functions with correct TypeScript types matching the backend schemas from #55a
- [ ] Route `/projects/new` is registered in `App.tsx` inside the protected layout, above `/projects/:projectId`
- [ ] `DashboardPage` renders a "New Project" button/link that navigates to `/projects/new`
- [ ] `NewProjectPage` renders four flow type cards: Brainstorm, Guided Interview, From Notes, From Repository -- each with a title and description
- [ ] Selecting a flow type on `NewProjectPage` calls `POST /api/project-flow/start` with the correct `flow_type` value and transitions to the chat UI
- [ ] `FlowChat` renders one input field per question from `first_questions` / `next_questions`
- [ ] `FlowChat` submit button calls `POST /api/project-flow/{flow_id}/respond` with correctly shaped `{answers: [{question_id, answer}]}` payload
- [ ] When `respond` returns `next_questions` (non-null), `FlowChat` replaces the current questions with the new batch
- [ ] When `respond` returns `brief` (non-null), the wizard transitions to `BriefReview`
- [ ] `BriefReview` displays all brief fields: name, description, tech_stack, architecture, open_decisions, suggested_sessions
- [ ] `BriefReview` allows editing the project name and description before finalizing
- [ ] Clicking "Create Project" on `BriefReview` calls `POST /api/project-flow/{flow_id}/finalize`
- [ ] After successful finalization, the app navigates to `/projects/{project_id}` using the `project_id` from the response
- [ ] Loading states are shown during API calls (start, respond, finalize)
- [ ] Error states are shown when API calls fail (network error, 4xx/5xx responses)
- [ ] `cd web && npx vitest run` passes with 15+ new tests across the new files

## Test Scenarios

### Unit: API client (`web/src/test/projectFlow.test.ts`)
- `startFlow` calls `apiClient.post("/api/project-flow/start", ...)` with correct body and returns parsed JSON
- `respondToFlow` calls `apiClient.post("/api/project-flow/{flowId}/respond", ...)` with answers array
- `finalizeFlow` calls `apiClient.post("/api/project-flow/{flowId}/finalize", ...)` and returns parsed result
- API functions throw on non-ok responses

### Unit: NewProjectPage (`web/src/test/NewProjectPage.test.tsx`)
- Renders four flow type cards with expected titles (Brainstorm, Guided Interview, From Notes, From Repository)
- Clicking a card calls `startFlow` with the correct `flow_type` enum value
- Shows loading indicator while `startFlow` is pending
- Shows error message when `startFlow` rejects
- After successful `startFlow`, renders `FlowChat` with the returned `first_questions`

### Unit: FlowChat (`web/src/test/FlowChat.test.tsx`)
- Renders one input field per question object passed in props
- Displays question text as label for each input
- Submit button is disabled when any answer is empty
- Clicking submit calls `respondToFlow` with `{answers: [{question_id, answer}]}` matching the inputs
- Shows loading state during submit
- When response has `next_questions`, re-renders with new question fields
- When response has `brief`, calls the `onBriefReady` callback with the brief object
- Shows error message when `respondToFlow` rejects

### Unit: BriefReview (`web/src/test/BriefReview.test.tsx`)
- Renders project name in an editable input field
- Renders project description in an editable textarea
- Renders tech stack entries
- Renders each suggested session's name, mission, and mode
- Renders open decisions list
- Editing name updates the displayed value
- Clicking "Create Project" calls `finalizeFlow` with the flow_id
- Shows loading state during finalization
- Shows error message when `finalizeFlow` rejects

### Unit: DashboardPage -- New Project button (`web/src/test/DashboardPage.test.tsx`)
- "New Project" button/link is rendered on the dashboard
- "New Project" button/link has `href="/projects/new"` or navigates to `/projects/new` on click

### Integration: Full wizard flow (`web/src/test/NewProjectFlow.test.tsx`)
- Mock all three API functions
- Render `NewProjectPage` in a `MemoryRouter`
- Select "Guided Interview" card -> verify `startFlow` called with `flow_type: "interview"`
- Answer questions in `FlowChat` -> submit -> verify `respondToFlow` called
- Mock response with `brief` -> verify `BriefReview` renders with brief data
- Click "Create Project" -> verify `finalizeFlow` called -> verify navigation to `/projects/{id}`

## Dependencies

- Depends on: #55a (backend endpoints -- done), #14 (React app scaffolding -- done), #15 (project dashboard -- done)

## Log

### [SWE] 2026-03-16 12:25
- Implemented full new project flow frontend wizard
- Created API client module with typed interfaces matching backend schemas
- Created FlowChat component with question rendering, grouped by category, answer collection, loading/error states
- Created BriefReview component with editable name/description, tech stack, architecture, open decisions, suggested sessions display, finalize button with loading/error states
- Created NewProjectPage with 4 flow type cards (Brainstorm, Guided Interview, From Notes, From Repository), initial input for notes/repo types, step transitions (select -> chat -> review -> navigate)
- Added /projects/new route in App.tsx above /projects/:projectId to avoid conflict
- Added "New Project" link button to DashboardPage header (visible in all states: loading, error, empty, populated)
- Files created:
  - web/src/api/projectFlow.ts
  - web/src/components/project-flow/FlowChat.tsx
  - web/src/components/project-flow/BriefReview.tsx
  - web/src/pages/NewProjectPage.tsx
  - web/src/test/projectFlow.test.ts (6 tests)
  - web/src/test/NewProjectPage.test.tsx (5 tests)
  - web/src/test/FlowChat.test.tsx (10 tests)
  - web/src/test/BriefReview.test.tsx (10 tests)
  - web/src/test/NewProjectFlow.test.tsx (2 integration tests)
- Files modified:
  - web/src/App.tsx (added route + import)
  - web/src/pages/DashboardPage.tsx (added New Project link, refactored to shared DashboardHeader)
  - web/src/test/DashboardPage.test.tsx (added 2 tests for New Project button)
- Tests added: 35 new tests across 6 test files
- Build results: 445 tests pass (89 files), 0 fail, build clean
- Known limitations: none

### [QA] 2026-03-16 12:31
- Tests: 445 passed, 0 failed (89 test files); 40 tests across the 6 new/modified test files
- Build: clean (tsc + vite build, no errors)
- Acceptance criteria:
  1. `web/src/api/projectFlow.ts` exports `startFlow`, `respondToFlow`, `finalizeFlow` with correct TS types: PASS
  2. Route `/projects/new` registered in App.tsx inside protected layout, above `/projects/:projectId`: PASS (line 31 vs line 32)
  3. DashboardPage renders "New Project" link navigating to `/projects/new`: PASS (DashboardHeader component with `<Link to="/projects/new">`)
  4. NewProjectPage renders four flow type cards (Brainstorm, Guided Interview, From Notes, From Repository) with title and description: PASS
  5. Selecting a flow type calls `POST /api/project-flow/start` with correct `flow_type` and transitions to chat: PASS
  6. FlowChat renders one input field per question: PASS (textarea per question with label)
  7. FlowChat submit calls `POST /api/project-flow/{flow_id}/respond` with `{answers: [{question_id, answer}]}`: PASS
  8. When respond returns `next_questions`, FlowChat replaces current questions with new batch: PASS
  9. When respond returns `brief`, wizard transitions to BriefReview: PASS
  10. BriefReview displays all brief fields (name, description, tech_stack, architecture, open_decisions, suggested_sessions): PASS
  11. BriefReview allows editing project name and description: PASS (editable input and textarea with state)
  12. Clicking "Create Project" calls `POST /api/project-flow/{flow_id}/finalize`: PASS
  13. After successful finalization, navigates to `/projects/{project_id}`: PASS (via onFinalized callback + useNavigate)
  14. Loading states shown during API calls (start, respond, finalize): PASS ("Starting flow...", "Submitting...", "Creating...")
  15. Error states shown when API calls fail: PASS (error messages rendered for all three endpoints)
  16. 15+ new tests: PASS (35 new tests across 6 files, well above threshold)
- VERDICT: PASS

### [PM] 2026-03-16 12:40
- Reviewed diff: 13 files (6 new, 4 modified, plus issue tracker files)
- Results verified: real data present -- 445 tests pass (89 files), 35 new tests across 6 test files, build clean
- Acceptance criteria: all 16 met
  1. API client exports startFlow, respondToFlow, finalizeFlow with correct TS types: MET
  2. Route /projects/new in App.tsx inside protected layout, above /projects/:projectId: MET
  3. DashboardPage "New Project" link navigating to /projects/new: MET (DashboardHeader, all 4 states)
  4. Four flow type cards (Brainstorm, Guided Interview, From Notes, From Repository): MET
  5. Selecting flow type calls POST /api/project-flow/start with correct flow_type: MET
  6. FlowChat renders one textarea per question with label: MET
  7. FlowChat submit sends {answers: [{question_id, answer}]} payload: MET
  8. next_questions replaces current questions: MET
  9. brief triggers transition to BriefReview: MET
  10. BriefReview displays all brief fields: MET
  11. BriefReview allows editing name and description: MET
  12. Create Project calls finalizeFlow: MET
  13. After finalization navigates to /projects/{project_id}: MET
  14. Loading states during API calls: MET (Starting flow.../Submitting.../Creating...)
  15. Error states when API calls fail: MET
  16. 15+ new tests: MET (35 new tests)
- Code quality: clean, follows existing patterns (API client style, component structure, test approach)
- Implementation notes: questions grouped by category, initial input field for From Notes/From Repository types, submit disabled until all answers filled
- Follow-up issues created: none needed
- VERDICT: ACCEPT
