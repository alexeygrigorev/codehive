# 55b: New Project Flow -- Frontend

## Description
Web UI wizard for guided project creation. User selects a flow type, goes through brainstorm/interview conversation, reviews the generated brief, and finalizes to create the project.

## Implementation Plan

### 1. Flow selection page
- `web/src/pages/NewProjectPage.tsx` -- entry point
- Four cards: "Brainstorm", "Guided Interview", "From Notes", "From Repository"
- Each card has description and icon
- Clicking a card starts the corresponding flow via `POST /api/project-flow/start`

### 2. Interview/brainstorm chat
- `web/src/components/project-flow/FlowChat.tsx` -- chat-like UI
- Shows agent questions, user types answers
- Batched questions displayed as a form (multiple inputs) or as chat bubbles
- Submit answers via `POST /api/project-flow/{flow_id}/respond`
- When brief is ready, transition to review step

### 3. Brief review
- `web/src/components/project-flow/BriefReview.tsx`
- Displays: project name (editable), description (editable), tech stack, architecture, open decisions, suggested sessions
- User can edit the brief before finalizing
- "Create Project" button calls `POST /api/project-flow/{flow_id}/finalize`

### 4. Success page
- After finalization, redirect to the new project's dashboard
- Show a summary of what was created (project + sessions)

### 5. Navigation
- Add "New Project" button to the project dashboard page
- Route: `/projects/new`

## Acceptance Criteria

- [ ] "New Project" button on dashboard navigates to `/projects/new`
- [ ] Four flow options are displayed with descriptions
- [ ] Selecting a flow starts the backend flow and shows the chat/form UI
- [ ] User can answer batched questions and see follow-up questions
- [ ] Brief review screen shows all generated fields (name, tech stack, sessions, open decisions)
- [ ] User can edit the brief before finalizing
- [ ] Finalizing creates the project and redirects to project dashboard
- [ ] Empty/error states are handled (API errors, empty responses)

## Test Scenarios

### Unit: FlowChat
- Render with mock questions, verify form fields appear
- Submit answers, verify API call with correct payload
- Render follow-up questions after response

### Unit: BriefReview
- Render with mock brief, verify all fields displayed
- Edit project name, verify state updates
- Click "Create Project", verify finalize API call

### Integration: Full wizard
- Start from NewProjectPage, select interview flow
- Answer questions, verify brief is generated
- Finalize, verify redirect to project page

## Dependencies
- Depends on: #55a (backend endpoints), #14 (React app), #15 (project dashboard)
