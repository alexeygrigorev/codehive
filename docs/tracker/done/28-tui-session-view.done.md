# 28: Terminal Client - Session View

## Description
Implement the TUI session view with chat display, ToDo list, action timeline, and changed files panels. The session screen is reached by selecting a session row on the ProjectDetailScreen (#27). All data is fetched via httpx from the backend REST API (same pattern as #27). A WebSocket client provides real-time event streaming so panels update live.

## Scope
- `backend/codehive/clients/terminal/screens/session.py` -- Session screen layout with panels (chat, todo, timeline, files)
- `backend/codehive/clients/terminal/widgets/chat.py` -- Chat panel: displays message history (role + content), has a text input for sending messages via POST /api/sessions/{id}/messages
- `backend/codehive/clients/terminal/widgets/todo.py` -- ToDo list panel: displays tasks from GET /api/sessions/{id}/tasks with status indicators
- `backend/codehive/clients/terminal/widgets/timeline.py` -- Action timeline panel: displays events from GET /api/sessions/{id}/events in chronological order
- `backend/codehive/clients/terminal/widgets/files.py` -- Changed files panel: displays file diffs from GET /api/sessions/{id}/diffs with additions/deletions counts
- `backend/codehive/clients/terminal/ws_client.py` -- WebSocket client that connects to /api/sessions/{id}/ws and dispatches incoming events to update TUI widgets
- `backend/codehive/clients/terminal/api_client.py` -- Add convenience methods: get_session, list_tasks, list_events, get_diffs, post_message
- `backend/codehive/clients/terminal/screens/project_detail.py` -- Add session row selection handler that pushes SessionScreen
- `backend/tests/test_tui_session.py` -- TUI session view tests

## Dependencies
- Depends on: #27 (TUI app shell and navigation) -- DONE
- Depends on: #07 (WebSocket endpoint for live events) -- DONE
- Depends on: #09 (engine adapter for sending messages) -- DONE

## Out of Scope
- Sub-agent tree view panel (future issue -- orchestration UI)
- Approval prompts inline in chat (future issue)
- Session mode switcher from TUI (future issue)
- Message streaming / partial message display (messages are shown once complete)

## Acceptance Criteria

- [ ] `SessionScreen` is a Textual `Screen` subclass that accepts a `session_id` parameter and displays session data
- [ ] Selecting a session row in `ProjectDetailScreen` pushes `SessionScreen` for that session's ID
- [ ] Session screen layout has four visible panels: Chat, ToDo, Timeline, Changed Files -- arranged with chat on the left, sidebar panels (ToDo, Timeline, Files) stacked on the right
- [ ] Chat panel displays message history fetched from the backend (via events with type `message.created` from GET /api/sessions/{id}/events, filtered for message events) showing role (user/assistant/system) and content
- [ ] Chat panel has a text input at the bottom; pressing Enter sends the message via POST /api/sessions/{id}/messages and appends it to the chat display
- [ ] ToDo panel lists tasks from GET /api/sessions/{id}/tasks showing title and status, with StatusIndicator widget reused from #27
- [ ] Timeline panel lists events from GET /api/sessions/{id}/events showing event type and timestamp in chronological order
- [ ] Changed Files panel lists files from GET /api/sessions/{id}/diffs showing file path, additions count (+N), and deletions count (-N)
- [ ] `APIClient` gains new convenience methods: `get_session(session_id)`, `list_tasks(session_id)`, `list_events(session_id, limit, offset)`, `get_diffs(session_id)`, `post_message(session_id, content)`
- [ ] `post_message` uses httpx `POST` (not GET) to send messages to the backend
- [ ] `WSClient` connects to `ws://{base_url}/api/sessions/{id}/ws` and receives JSON event messages
- [ ] `WSClient` runs in a background thread (Textual `@work(thread=True)`) and posts received events to the Textual message queue so widgets can react
- [ ] When a WebSocket event arrives, the relevant panel updates: new messages appear in chat, task status changes reflect in ToDo, new events appear in timeline, file changes update the files panel
- [ ] Keyboard navigation: Escape/Backspace goes back to ProjectDetailScreen, Tab/Shift-Tab cycles between panels, q quits
- [ ] Footer with key bindings is displayed on the session screen
- [ ] Panels display "No data" or equivalent placeholder text when the session has no messages/tasks/events/diffs
- [ ] All HTTP calls use `@work(thread=True)` to avoid blocking the Textual UI thread (same pattern as #27)
- [ ] `uv run pytest tests/test_tui_session.py -v` passes with 15+ tests
- [ ] All existing TUI tests (`tests/test_tui.py`) continue to pass

## Test Scenarios

### Unit: APIClient new methods
- `get_session(session_id)` calls GET /api/sessions/{session_id} and returns parsed JSON
- `list_tasks(session_id)` calls GET /api/sessions/{session_id}/tasks and returns parsed JSON
- `list_events(session_id)` calls GET /api/sessions/{session_id}/events and returns parsed JSON
- `get_diffs(session_id)` calls GET /api/sessions/{session_id}/diffs and returns parsed JSON
- `post_message(session_id, content)` calls POST /api/sessions/{session_id}/messages with correct body

### Unit: Chat widget
- ChatPanel renders message history from provided data (list of role/content dicts)
- ChatPanel shows role labels (user/assistant/system) with distinct visual styling
- ChatPanel input field exists and is focusable
- ChatPanel displays "No messages" when message list is empty

### Unit: ToDo widget
- TodoPanel renders task list with title and status for each task
- TodoPanel reuses StatusIndicator for task status display
- TodoPanel displays "No tasks" when task list is empty

### Unit: Timeline widget
- TimelinePanel renders events with type and formatted timestamp
- TimelinePanel displays events in chronological order (oldest first)
- TimelinePanel displays "No events" when event list is empty

### Unit: Changed Files widget
- FilesPanel renders file paths with +N/-N addition/deletion counts
- FilesPanel displays "No changes" when diff list is empty

### Unit: Session screen composition
- SessionScreen composes and mounts with all four panels visible (using Textual's App.run_test with mocked API)
- SessionScreen fetches session, tasks, events, and diffs on mount via APIClient (verify mock calls)
- SessionScreen populates all four panels with mocked data
- Pressing Escape on SessionScreen pops back to previous screen

### Unit: WebSocket client
- WSClient can be instantiated with a base URL and session ID
- WSClient builds the correct WebSocket URL (ws:// scheme from http://, wss:// from https://)
- WSClient dispatches received events by calling a provided callback

### Integration: Navigation flow
- From ProjectDetailScreen, selecting a session row pushes SessionScreen with correct session_id
- Full navigation: Dashboard -> ProjectList -> ProjectDetail -> Session -> back (Escape) -> ProjectDetail

## Technical Notes
- Follow the exact same patterns established in #27: `@work(thread=True)` for HTTP, `app.call_from_thread` to update UI, `MagicMock(spec=APIClient)` in tests
- The session screen layout should use Textual's `Horizontal` and `Vertical` containers for the two-column layout (chat left, sidebar right)
- Messages are retrieved from the events endpoint filtered for `message.created` type, OR from the logs endpoint -- use whichever provides role + content. The events endpoint (GET /api/sessions/{id}/events) returns events with `type` and `data` (JSONB) fields
- The `post_message` method on APIClient needs to use `self._client.post()` rather than `self._client.get()`
- WebSocket client should use `httpx_ws` or `websockets` library (check what is already in pyproject.toml; if neither, add `websockets`)
- For tests, mock the APIClient entirely (same as test_tui.py) -- do NOT require a running backend or Redis
- For WebSocket tests, mock at the WSClient level -- do not test actual WebSocket connections
- The session status bar at the top of SessionScreen should show: session name, engine, mode, and current status (reusing StatusIndicator)

## Log

### [SWE] 2026-03-15 12:00
- Implemented full TUI session view with all four panels (Chat, ToDo, Timeline, Changed Files)
- Created ChatPanel with message history display, role styling, and input field for sending messages
- Created TodoPanel reusing StatusIndicator from #27 for task status display
- Created TimelinePanel displaying events in chronological order with formatted timestamps
- Created FilesPanel showing file paths with +N/-N addition/deletion counts
- Created WSClient using websockets library for live event streaming via background thread
- Extended APIClient with 6 new methods: get_session, list_tasks, list_events, get_diffs, post_message, and low-level post
- Added session row selection handler to ProjectDetailScreen that pushes SessionScreen
- SessionScreen uses two-column layout (Horizontal/Vertical) with chat on left, sidebar panels stacked on right
- Session header bar shows session name, engine, mode, and StatusIndicator
- All HTTP calls use @work(thread=True), UI updates via app.call_from_thread (same pattern as #27)
- WebSocket events dispatch to relevant panels: message.created -> chat, task.* -> reload tasks, file.changed -> reload diffs, all -> timeline
- Keyboard navigation: Escape/Backspace goes back, Tab/Shift-Tab cycles panels, q quits
- Empty state placeholders: "No messages", "No tasks", "No events", "No changes"
- Files created:
  - backend/codehive/clients/terminal/widgets/chat.py
  - backend/codehive/clients/terminal/widgets/todo.py
  - backend/codehive/clients/terminal/widgets/timeline.py
  - backend/codehive/clients/terminal/widgets/files.py
  - backend/codehive/clients/terminal/ws_client.py
  - backend/codehive/clients/terminal/screens/session.py
  - backend/tests/test_tui_session.py
- Files modified:
  - backend/codehive/clients/terminal/api_client.py (added post, get_session, list_tasks, list_events, get_diffs, post_message)
  - backend/codehive/clients/terminal/screens/project_detail.py (added on_data_table_row_selected handler)
- Tests added: 28 tests covering all test scenarios from the issue
- Build results: 48 tests pass (28 new + 20 existing), 0 fail, ruff clean
- Known limitations: None

### [QA] 2026-03-15 13:00
- Tests: 48 passed (28 new in test_tui_session.py + 20 existing in test_tui.py), 0 failed
- Ruff check: clean (all checks passed)
- Ruff format: clean (all files already formatted)
- Acceptance criteria:
  - SessionScreen is a Screen subclass with session_id parameter: PASS
  - Selecting session row in ProjectDetailScreen pushes SessionScreen: PASS
  - Four visible panels (Chat left, ToDo/Timeline/Files stacked right): PASS
  - Chat panel displays message history from message.created events: PASS
  - Chat panel input sends via POST and appends to display: PASS
  - ToDo panel lists tasks with StatusIndicator: PASS
  - Timeline panel lists events with type and timestamp chronologically: PASS
  - Changed Files panel shows path with +N/-N counts: PASS
  - APIClient gains get_session, list_tasks, list_events, get_diffs, post_message: PASS
  - post_message uses httpx POST (not GET): PASS
  - WSClient connects to correct ws:// URL: PASS
  - WSClient runs in background thread, dispatches via call_from_thread: PASS
  - WebSocket events update relevant panels: PASS
  - Keyboard navigation (Escape/Backspace/Tab/Shift-Tab/q): PASS
  - Footer with key bindings displayed: PASS
  - Empty state placeholders (No messages/tasks/events/changes): PASS
  - All HTTP calls use @work(thread=True): PASS
  - 15+ tests in test_tui_session.py: PASS (28 tests)
  - All existing TUI tests continue to pass: PASS
- Note: unrelated deletion of docs/tracker/14-react-app-scaffolding.todo.md detected in working tree -- this should be reverted as it is not part of issue #28
- VERDICT: PASS

### [PM] 2026-03-15 14:30
- Reviewed diff: 9 files changed (7 new, 2 modified) plus the in-progress tracker file
- Results verified: real data present -- 48 tests pass (28 new + 20 existing), all green in 6.18s
- Acceptance criteria: all 19 met
  - SessionScreen is a Screen subclass with session_id parameter: MET
  - Session row selection in ProjectDetailScreen pushes SessionScreen: MET
  - Four-panel layout (Chat left, ToDo/Timeline/Files right): MET
  - Chat panel displays message history from message.created events with role labels: MET
  - Chat input sends via POST, appends optimistically: MET
  - ToDo panel lists tasks with StatusIndicator reuse: MET
  - Timeline panel shows events chronologically with formatted timestamps: MET
  - Changed Files panel shows path with +N/-N counts: MET
  - APIClient gains get_session, list_tasks, list_events, get_diffs, post_message + post base: MET
  - post_message uses httpx POST (verified by test asserting GET not called): MET
  - WSClient builds correct ws:// / wss:// URLs: MET
  - WSClient runs in @work(thread=True), dispatches via call_from_thread: MET
  - WebSocket events route to correct panels (message->chat, task->reload, file->reload, all->timeline): MET
  - Keyboard navigation (Escape/Backspace/Tab/Shift-Tab/q): MET
  - Footer with key bindings displayed: MET
  - Empty state placeholders for all panels: MET
  - All HTTP calls use @work(thread=True): MET
  - 15+ tests (28 actual): MET
  - Existing TUI tests pass (20 tests): MET
- Code quality: clean, follows #27 patterns exactly (mocked APIClient, @work decorators, call_from_thread)
- Tests are meaningful: verify widget composition, data population, navigation, API correctness, WS URL building, event dispatching
- WARNING: working tree contains unrelated deletion of docs/tracker/14-react-app-scaffolding.todo.md -- must be reverted before commit
- Follow-up issues created: none needed
- VERDICT: ACCEPT
