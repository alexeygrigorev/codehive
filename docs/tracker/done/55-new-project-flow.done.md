# 55: New Project Flow UI (Parent)

## Description
Guided project creation: brainstorm/interview/spec-from-notes/start-from-repo options, auto-generated briefs, suggested sessions. Currently project creation is manual CRUD -- this adds structured onboarding. Split into backend and frontend.

## Sub-Issues
- **55a** -- Backend: interview/brainstorm endpoints, project brief generation, suggested sessions
- **55b** -- Frontend: new project wizard UI with flow selection, interview chat, brief review

## Dependencies
- Depends on: #14 (React app), #45 (agent modes), #48 (knowledge base)

## Log

### [SWE] 2026-03-18 10:00
- Parent issue #55 is a tracker for sub-issues #55a (backend) and #55b (frontend)
- Both sub-issues are already completed and accepted (in docs/tracker/done/)
- Verified all existing code and tests still pass:
  - Backend: 30 project flow tests pass, ruff check clean, ruff format clean
  - Frontend: 623 tests pass (including 35+ project flow tests), tsc --noEmit clean
- No new code or tests needed -- this parent issue is ready to close
- Files modified: none (parent issue only)
- Tests added: 0 (all tests were added in #55a and #55b)
- Build results: all tests pass, lint clean
- Known limitations: none
