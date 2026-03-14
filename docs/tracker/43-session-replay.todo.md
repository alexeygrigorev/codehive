# 43: Session Replay

## Description
Implement session replay: the ability to open any completed session and step through its full history of actions chronologically. Shows messages, tool calls, file changes, and terminal output in sequence.

## Scope
- `backend/codehive/core/replay.py` -- Replay data builder: reconstruct ordered action sequence from events/messages/diffs
- `backend/codehive/api/routes/replay.py` -- Endpoint to fetch replay data for a session (paginated timeline of all actions)
- `web/src/pages/ReplayPage.tsx` -- Replay viewer with step-through controls (previous/next/play/pause)
- `web/src/components/ReplayTimeline.tsx` -- Visual timeline with scrubber
- `web/src/components/ReplayStep.tsx` -- Individual step rendering (message, tool call, file change)
- `backend/tests/test_replay.py` -- Replay data builder tests

## Dependencies
- Depends on: #07 (events table for action history)
- Depends on: #14 (React app scaffolding)
- Depends on: #16 (message rendering components to reuse)
