# 53d: Mobile Questions and Approvals Screens

## Description
Build screens for viewing and answering pending questions, and for viewing and acting on pending approval requests.

## Implementation Plan

### 1. Questions screen
- `mobile/src/screens/QuestionsScreen.tsx` -- FlatList of pending questions across all sessions
- Each item: question text, session name, project name, timestamp
- Tapping opens inline text input to answer
- After answering, item moves to "answered" state with visual feedback

### 2. Approvals screen
- `mobile/src/screens/ApprovalsScreen.tsx` -- FlatList of pending approvals
- Each item: action description, session name, approve/reject buttons inline
- After action, item is removed from list with animation

### 3. Shared components
- `mobile/src/components/QuestionCard.tsx` -- question with inline answer input
- `mobile/src/components/ApprovalCard.tsx` -- approval with inline action buttons

### 4. Badge counts
- Questions tab and Approvals tab show badge count of pending items
- Counts update live via WebSocket events

## Acceptance Criteria

- [ ] Questions screen lists all pending questions from all sessions
- [ ] User can tap a question and type an answer inline
- [ ] After answering, the question shows as answered
- [ ] Approvals screen lists all pending approval requests
- [ ] User can approve or reject directly from the list
- [ ] Tab badge counts show number of pending items
- [ ] Counts update in real-time via WebSocket

## Test Scenarios

### Unit: QuestionCard
- Render with unanswered question, verify input is available
- Submit an answer, verify API call is made
- Render answered question, verify answer is shown

### Unit: ApprovalCard
- Render with pending approval, verify approve/reject buttons
- Tap approve, verify API call is made and card is removed

### Integration: Questions flow
- Load QuestionsScreen with mocked API, verify list renders
- Answer a question, verify list updates

## Dependencies
- Depends on: #53a (scaffolding + API client)
