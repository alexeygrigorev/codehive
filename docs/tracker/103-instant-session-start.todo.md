# Issue #103: Instant session start — click New Session, land in chat

## Problem

Currently "New Session" opens a form asking for name, engine, mode before you can start chatting. This is friction. The user just wants to start talking to the agent immediately.

## Requirements

- [ ] Clicking "New Session" immediately creates a session and opens the chat view
- [ ] Session name is auto-generated from the first message (e.g., first 50 chars, or "Session YYYY-MM-DD HH:MM")
- [ ] Session name updates after the first message is sent (backend PATCH /api/sessions/{id})
- [ ] Mode selector is available IN the chat view (already exists as SessionModeSwitcher) — default to "execution"
- [ ] Engine is always "native" by default — no need to choose
- [ ] Remove the session creation form from the project page
- [ ] Keep the "+ New Session" button, but it goes straight to chat

## Flow

1. User clicks "+ New Session" on project page
2. POST /api/projects/{id}/sessions with name="New Session", engine="native", mode="execution"
3. Navigate to /sessions/{new_session_id}
4. User types first message
5. After first message, PATCH /api/sessions/{id} with name derived from the message content

## Notes

- The mode switcher already exists in the session header — no new UI needed for mode selection
- The session creation form (engine/mode/issue-link) can be removed entirely from ProjectPage
- If the user wants to link to an issue, they can do it later from the session settings
