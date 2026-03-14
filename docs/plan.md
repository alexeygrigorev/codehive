# Codehive - Implementation Plan

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend API | Python (FastAPI) | Async, fast, matches existing codebase |
| Database | PostgreSQL | Relational model fits entities well |
| Queue / Pub-Sub | Redis | Task queues, event streaming, pub/sub |
| Realtime | WebSocket (FastAPI) + SSE | Live updates to all clients |
| Agent Runtime | Python (asyncio workers) | Shell, git, file ops per session |
| Frontend Web | React + Vite | Fast, component-based, good ecosystem |
| Terminal Client | Python (Textual) | Rich TUI, same language as backend |
| Mobile | PWA first, then React Native | PWA gets us 80% for free |
| Telegram | python-telegram-bot | Thin adapter over backend API |
| LLM Integration | Anthropic SDK + Claude Code CLI | Native agent + Claude Code bridge |

## Phase 0 — Foundation

**Goal:** Project skeleton, database, basic API, minimal CLI.

### 0.1 Project Structure
```
codehive/                            # repo root (monorepo)
├── backend/                         # Python project
│   ├── codehive/                    # Python package
│   │   ├── __init__.py
│   │   ├── __version__.py
│   │   ├── cli.py                   # CLI entry point
│   │   ├── config.py                # Settings (env-based)
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models
│   │   │   ├── migrations/          # Alembic
│   │   │   └── session.py           # DB session factory
│   │   ├── api/
│   │   │   ├── app.py               # FastAPI app
│   │   │   ├── routes/
│   │   │   │   ├── projects.py
│   │   │   │   ├── sessions.py
│   │   │   │   ├── tasks.py
│   │   │   │   └── events.py
│   │   │   └── ws.py                # WebSocket handlers
│   │   ├── core/
│   │   │   ├── workspace.py         # Workspace manager
│   │   │   ├── project.py           # Project operations
│   │   │   ├── session.py           # Session lifecycle
│   │   │   ├── task_queue.py        # ToDo/task queue logic
│   │   │   └── events.py            # Event bus (Redis pub/sub)
│   │   ├── engine/
│   │   │   ├── base.py              # Engine adapter interface
│   │   │   ├── native.py            # Native agent engine
│   │   │   └── claude_code.py       # Claude Code CLI bridge
│   │   ├── execution/
│   │   │   ├── shell.py             # Shell runner
│   │   │   ├── file_ops.py          # File operations
│   │   │   ├── git_ops.py           # Git operations
│   │   │   └── diff.py              # Diff computation
│   │   └── clients/
│   │       ├── telegram/
│   │       └── terminal/
│   ├── tests/
│   ├── pyproject.toml
│   ├── Makefile
│   └── alembic.ini
├── web/                             # React frontend (Phase 2)
├── docs/                            # Documentation
├── docker-compose.yml               # Postgres + Redis
├── README.md
├── LICENSE
└── .gitignore
```

### 0.2 Database Models
Core tables:
- `workspaces` — id, name, root_path, settings (JSONB), created_at
- `projects` — id, workspace_id, name, path, description, archetype, knowledge (JSONB), created_at
- `issues` — id, project_id, title, description, status, github_issue_id, created_at
- `sessions` — id, project_id, issue_id (nullable), parent_session_id (nullable), name, engine, mode, status, config (JSONB), created_at
- `tasks` — id, session_id, title, instructions, status, priority, depends_on, mode (auto/manual), created_by, created_at
- `messages` — id, session_id, role (user/assistant/system/tool), content, metadata (JSONB), created_at
- `events` — id, session_id, type, data (JSONB), created_at
- `checkpoints` — id, session_id, git_ref, state (JSONB), created_at
- `pending_questions` — id, session_id, question, context, answered, answer, created_at

### 0.3 Deliverables
- [ ] FastAPI app with health check
- [ ] PostgreSQL + Redis via docker-compose
- [ ] Alembic migrations for all core tables
- [ ] Config via environment variables
- [ ] `codehive serve` CLI command to start the server
- [ ] Basic CRUD endpoints for projects and sessions

---

## Phase 1 — Session Engine (Core Loop)

**Goal:** A single session can execute tasks: send messages to LLM, run shell commands, edit files, track diffs.

### 1.1 Engine Adapter Interface
```python
class EngineAdapter(Protocol):
    async def create_session(self, project_id, config) -> str
    async def send_message(self, session_id, message) -> AsyncIterator[Event]
    async def start_task(self, session_id, task_id) -> None
    async def pause(self, session_id) -> None
    async def resume(self, session_id) -> None
    async def approve_action(self, session_id, action_id) -> None
    async def reject_action(self, session_id, action_id) -> None
    async def get_diff(self, session_id) -> Diff
```

### 1.2 Native Engine
- Anthropic SDK (Claude) as the LLM
- Tool definitions: edit_file, read_file, run_shell, git_commit, search_files
- Conversation loop with tool use
- Streams events: `message.created`, `tool.call.started`, `tool.call.finished`, `file.changed`

### 1.3 Execution Layer
- **Shell runner** — async subprocess execution, stdout/stderr streaming, timeout
- **File ops** — read, write, edit, glob, grep (sandboxed to project root)
- **Git ops** — status, diff, commit, checkout, branch, log
- **Diff service** — compute file diffs, track changed files per session

### 1.4 Event Bus
- Redis pub/sub for real-time events
- All engine events published to `session:{id}:events` channel
- Persistent storage in `events` table
- Clients subscribe via WebSocket

### 1.5 Task Queue / Scheduler
- Session checks ToDo after completing a task
- If `queue_enabled` and tasks remain: auto-start next task
- If agent asks a question and tasks remain: save question to pending, continue
- State machine: `idle -> planning -> executing -> waiting_input -> ...`

### 1.6 Deliverables
- [ ] Native engine with Anthropic SDK
- [ ] Tool implementations (shell, file, git)
- [ ] Event bus (Redis pub/sub + DB persistence)
- [ ] Task queue with auto-next logic
- [ ] Pending questions queue
- [ ] Session state machine
- [ ] WebSocket endpoint for live event streaming
- [ ] `codehive session create <project>` CLI command
- [ ] `codehive session chat <session_id>` interactive CLI chat

---

## Phase 2 — Web App

**Goal:** Browser-based application for managing projects and sessions. Lives in `web/` directory.

### 2.1 Tech Stack
- React + TypeScript + Vite
- Tailwind CSS for styling
- WebSocket client for real-time updates

### 2.2 Project Dashboard
- List of projects
- Per project: active sessions, recent issues, status indicators

### 2.3 Session View (Core Screen)
Layout:
```
+------------------+-------------------+
|     Chat         |   Sidebar         |
|                  |   - ToDo          |
|                  |   - Changed Files |
|                  |   - Sub-agents    |
|                  |   - Timeline      |
+------------------+-------------------+
```

- Chat with streaming messages
- Live ToDo progress
- File diff viewer (inline)
- Timeline of agent actions
- Session mode indicator (Brainstorm/Interview/Planning/Execution/Review)
- Approval prompts inline

### 2.4 Real-time Updates
- WebSocket connection per session
- Live message streaming
- Live ToDo status updates
- Live diff updates
- Notification badges for pending questions / approvals

### 2.5 Deliverables
- [ ] React app scaffolding in `web/` (Vite + TypeScript + Tailwind)
- [ ] Project list + project dashboard
- [ ] Session view with chat, ToDo, files, timeline panels
- [ ] WebSocket integration for live updates
- [ ] Diff viewer component
- [ ] Session mode switcher
- [ ] Approval inline UI

---

## Phase 3 — Sub-Agents & Orchestration

**Goal:** Sessions can spawn sub-agent sessions. Orchestrator mode.

### 3.1 Sub-Agent Spawning
- `spawn_subagent` tool available to the engine
- Creates a new session with `parent_session_id`
- Sub-agent gets: mission, role, scope (file paths), playbook (optional)
- Runs independently, returns structured report on completion

### 3.2 Orchestrator Mode
- Session mode = `orchestrator`
- Agent plans, decomposes, spawns sub-agents
- Does NOT edit files directly
- Monitors sub-agent progress via events
- Aggregates reports, decides next steps

### 3.3 Sub-Agent Visibility (UI)
- Tree view in parent session sidebar
- Status per sub-agent (running/done/failed)
- Click to open sub-agent's full session
- Aggregated progress bar

### 3.4 Structured Reports
Sub-agent completion emits:
```json
{
  "status": "completed",
  "summary": "Implemented OAuth backend flow",
  "files_changed": ["auth_service.py", "oauth_controller.py"],
  "tests": {"added": 3, "passing": 3},
  "warnings": []
}
```

### 3.5 Deliverables
- [ ] `spawn_subagent` tool in engine
- [ ] Parent-child session relationship
- [ ] Orchestrator mode (no direct file edits)
- [ ] Structured report format + event
- [ ] Sub-agent tree view in web UI
- [ ] Aggregated progress display

---

## Phase 4 — Checkpoints, Roles & Playbooks

**Goal:** Safety net for rollbacks. Configurable agent behavior.

### 4.1 Checkpoints
- Auto-checkpoint before destructive operations
- Manual checkpoint via UI/CLI
- Checkpoint = git commit + session state snapshot (JSONB)
- Rollback: restore git state + session state
- UI: checkpoint list with restore button

### 4.2 Agent Roles
- Role definitions stored as YAML/JSON in workspace config
- Global roles + simple per-project overrides (no inheritance chains or extensions)
- Role includes: description, responsibilities, allowed tools, coding rules
- Roles assigned when spawning sub-agents

### 4.3 Project Archetypes
- Archetype = roles + default settings
- Stored in workspace config
- Selected at project creation time
- Clonable and customizable

### 4.5 Deliverables
- [ ] Checkpoint creation and storage
- [ ] Rollback (git + state)
- [ ] Role YAML format and loading
- [ ] Archetype selection at project creation
- [ ] UI for checkpoints and roles

---

## Phase 5 — Terminal Client

**Goal:** Full TUI client accessible via SSH.

### 5.1 Textual TUI App
Using Python Textual framework:
- Dashboard: active projects, sessions, pending questions, failed agents
- Project view: issues, sessions, status
- Session view: chat, ToDo, sub-agents, timeline, changed files
- Navigation: keyboard-driven

### 5.2 Command Mode
Non-interactive commands for scripting and emergencies:
```bash
codehive projects list
codehive sessions list --project myapp
codehive session status <id>
codehive session send <id> "fix the tests"
codehive session pause <id>
codehive session rollback <id> --checkpoint <cp_id>
codehive questions list
codehive questions answer <id> "use Google OAuth"
codehive system health
codehive system maintenance on
```

### 5.3 Rescue Mode
Minimal subset for phone-over-SSH:
- `codehive rescue` — shows: failed sessions, pending questions, system health
- One-command actions: stop, rollback, restart, answer

### 5.4 Deliverables
- [ ] Textual TUI with dashboard, project, session views
- [ ] All command-mode CLI commands
- [ ] Rescue mode
- [ ] WebSocket client for live updates in TUI

---

## Phase 6 — Telegram Bot

**Goal:** Lightweight control and monitoring from Telegram.

### 6.1 Commands
```
/projects          — list projects
/sessions          — active sessions
/status <session>  — session status + progress
/todo <session>    — view/add ToDo items
/send <session>    — send message to session
/approve <id>      — approve pending action
/reject <id>       — reject pending action
/questions         — list pending questions
/answer <id>       — answer a question
/stop <session>    — stop session
```

### 6.2 Notifications
Push notifications for:
- Approval required
- Session completed
- Session failed
- Sub-agent report ready
- Pending question added

### 6.3 Deliverables
- [ ] Telegram bot with all commands
- [ ] Push notifications
- [ ] Inline approval buttons
- [ ] Session status summaries

---

## Phase 7 — Claude Code Bridge

**Goal:** Use Claude Code subscription as an alternative engine.

### 7.1 CLI Bridge
- Spawn `claude` CLI process per session
- Parse stdout for events (tool calls, messages, diffs)
- Map to codehive event format
- Respect Claude Code's own approval flow

### 7.2 Engine Adapter
- Implements the same `EngineAdapter` interface
- Session can be started with `engine: claude_code`
- UI is identical regardless of engine

### 7.3 Deliverables
- [ ] Claude Code CLI wrapper
- [ ] Event parser (stdout -> codehive events)
- [ ] Engine adapter implementation
- [ ] Engine selection in session creation UI

---

## Phase 8 — GitHub Integration

**Goal:** Import GitHub Issues into codehive's internal tracker (one-way: GitHub -> codehive).

### 8.1 Issue Import
- Import GitHub issues into project issue tracker
- Webhook listener for new/updated GitHub issues
- Map GitHub labels/status to internal issue fields
- Periodic sync as fallback to webhooks

### 8.2 Auto-Session Trigger
- New GitHub issue -> suggest/auto-create codehive session
- Configurable: manual / suggest / auto

### 8.3 Future (Not MVP)
- Bidirectional sync (codehive -> GitHub issues) — add later if needed
- PR creation from session via `gh` CLI
- Auto-close GitHub issues when session completes

### 8.4 Deliverables
- [ ] GitHub token integration
- [ ] Issue import (one-way sync)
- [ ] Webhook handler for new/updated issues
- [ ] Auto-session trigger

---

## Phase 9 — Voice & Mobile

**Goal:** Voice input and mobile-optimized experience.

### 9.1 Voice Input
- Browser-based speech-to-text (Web Speech API)
- Whisper API as fallback for server-side STT
- Transcript preview before sending
- Route to appropriate chat level (global/project/session)

### 9.2 Mobile PWA
- Responsive web app optimized for mobile
- Push notifications via service worker
- Quick actions: approve, answer question, check status
- Voice input button

### 9.3 Deliverables
- [ ] Voice input in web UI
- [ ] PWA manifest + service worker
- [ ] Mobile-optimized layouts
- [ ] Push notifications

---

## Phase 10 — SSH & Remote Execution

**Goal:** Manage remote servers, SSH tunnels, port forwarding.

### 10.1 Remote Connector
- SSH connection manager (paramiko / asyncssh)
- Store targets: host, key, known_hosts
- Liveness checks, auto-reconnect

### 10.2 Tunnel Manager
- Port forwarding registry
- UI: list active tunnels, preview links, restart/close
- Auto-tunnel for dev server previews

### 10.3 Deliverables
- [ ] SSH connection manager
- [ ] Tunnel creation and lifecycle
- [ ] Tunnel UI in web and terminal clients
- [ ] Preview links

---

## Milestones Summary

| Phase | Name | Key Outcome |
|-------|------|-------------|
| 0 | Foundation | API server, DB, project/session CRUD |
| 1 | Session Engine | Agent can chat, run tools, stream events, work task queues |
| 2 | Web UI | Browser interface for projects and sessions |
| 3 | Sub-Agents | Orchestrator spawns sub-agent sessions |
| 4 | Safety & Config | Checkpoints, roles, playbooks, archetypes |
| 5 | Terminal Client | Full TUI + command mode + rescue |
| 6 | Telegram | Lightweight bot for control and notifications |
| 7 | Claude Code | Bridge to use Claude Code subscription |
| 8 | GitHub | Issue sync, PR creation, auto-sessions |
| 9 | Voice & Mobile | STT input, PWA, push notifications |
| 10 | Remote/SSH | SSH tunnels, remote execution |

**MVP = Phases 0-2**: A working agent that can be controlled from a web UI with live streaming, task queues, and diffs. This is the minimum to start using daily.

**Core product = Phases 0-5**: Adds sub-agents, safety, and terminal access. This is the full core vision.
