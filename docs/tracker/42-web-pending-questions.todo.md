# 42: Web Pending Questions UI

## Description
Build the pending questions interface in the web app. Users should see unanswered questions across all sessions, answer them from any client, and have answers injected back into the session context.

## Scope
- `web/src/pages/QuestionsPage.tsx` -- Global pending questions view (all sessions)
- `web/src/components/QuestionCard.tsx` -- Individual question display with answer input
- `web/src/components/sidebar/QuestionsPanel.tsx` -- Per-session pending questions in session sidebar
- `web/src/api/questions.ts` -- API hooks for listing and answering questions

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #10 (pending questions API)
