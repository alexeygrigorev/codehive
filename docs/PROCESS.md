# Development Process

## Overview

We use file-based issue tracking in `docs/tracker/`. Four agents handle the lifecycle: PM grooms, Engineer implements, Tester verifies, PM accepts.

Terminology:
- Issue = a file in `docs/tracker/` describing work to be done (bug fix, feature, etc.)
- Task = a Claude Code task panel item tracking pipeline steps within the current session

## Issue Lifecycle

```
PM grooms (.todo)  ->  Engineer builds (.in-progress)  ->  Tester verifies  ->  PM accepts (.done)
```

### File-Based Status

Issue status is encoded in the filename:

| Status | Filename Pattern | Meaning |
|--------|-----------------|---------|
| Todo | `01-name.todo.md` | Not started, needs PM grooming before pickup |
| Groomed | `01-name.groomed.md` | PM has groomed, ready for engineer |
| In Progress | `01-name.in-progress.md` | Engineer is working on it |
| Done | `done/01-name.done.md` | PM accepted, complete |

### Status Transitions

```
.todo.md  -->  PM grooms  -->  .groomed.md  -->  Engineer picks up  -->  .in-progress.md
                                                      |
                                              Engineer done + Tester pass + PM accept
                                                      |
                                                      v
                                              done/NN-name.done.md
```

## Orchestrator Role

The orchestrator (top-level Claude Code session) is a MANAGER, not an implementer. It:

- Launches agents (PM, SWE, QA) and routes work between them
- Routes rejection feedback: when QA fails, send SWE back with the QA feedback; when PM rejects, send SWE back with the PM feedback
- Commits code ONLY after PM accepts
- Picks next issues from the backlog
- Creates task panel items to track pipeline progress

The orchestrator NEVER writes or modifies code (backend/, web/). It only touches:
- docs/tracker/ files (creating issues, status transitions)
- Task panel items
- Git commits (after PM accepts)

## Agent Workflow

1. PM Grooms: Pick `.todo.md` issues, add acceptance criteria and test scenarios, rename to `.groomed.md`
2. Pick 2 issues: Select the lowest-numbered `.groomed.md` issues whose dependencies are met
3. SWE implements: Write code + tests, rename to `.in-progress.md`
4. QA reviews: Run tests, verify acceptance criteria, report PASS/FAIL
5. If QA FAIL: Launch SWE agent again with QA's feedback. SWE fixes. Then launch QA again. Repeat until QA passes.
6. If QA PASS: Launch PM for acceptance review
7. If PM rejects: Launch SWE agent again with PM's feedback. SWE fixes. Then QA re-verifies. Then PM re-reviews. Repeat until PM accepts.
8. If PM accepts: Orchestrator renames to `.done.md` and commits
9. Pick next 2 issues and repeat

### Done Means DONE

An issue moves to `.done.md` ONLY when ALL acceptance criteria are fully satisfied and verified. Writing code is not done. Passing tests is not done. The actual deliverable must be complete:

- "API endpoint" is done when it returns correct responses — not when the route is registered
- "Database migration" is done when the schema is applied and queries work — not when the migration file exists
- "WebSocket streaming" is done when events stream to connected clients — not when the handler is written

If the deliverable requires actual verification beyond tests, the issue stays `.in-progress.md` until that happens.

**IMPORTANT: One agent per issue.** Every agent invocation handles exactly ONE issue. When working on 2 issues in a batch, launch 2 separate agents in parallel — never combine multiple issues into a single agent call.

### Rejection Loop

```
QA FAIL  -->  SWE fixes (with QA feedback)  -->  QA re-verifies  -->  repeat until PASS
PM REJECT --> SWE fixes (with PM feedback)  -->  QA re-verifies  -->  PM re-reviews --> repeat until ACCEPT
```

The orchestrator's job in a rejection is to launch a new SWE agent with the rejection details, NOT to fix the code itself.

### Issue Log (Communication via Issue File)

Every agent MUST append log entries to the issue file as they work. The issue file is the single source of truth for what happened.

Each agent appends a `## Log` section (or appends to it) with timestamped entries:

```markdown
## Log

### [SWE] 2026-03-14 12:30
- Started implementation
- Created FastAPI app with health endpoint
- Added SQLAlchemy models for Project and Session
- Tests added: 8 unit tests, 3 integration tests
- Build: 11 tests pass, 0 fail, ruff clean
- Files modified: backend/codehive/api/app.py, backend/codehive/db/models.py

### [QA] 2026-03-14 13:15
- Tests: 11 passed, 0 failed
- Ruff: clean
- Acceptance criteria 1-4: PASS
- Acceptance criterion 5: FAIL — health endpoint missing version field
- VERDICT: FAIL

### [SWE] 2026-03-14 13:45
- Fixed health endpoint to include __version__
- Tests: 12 pass, 0 fail
- Files modified: backend/codehive/api/app.py, backend/tests/test_api.py

### [QA] 2026-03-14 14:00
- All criteria pass
- VERDICT: PASS

### [PM] 2026-03-14 14:30
- Reviewed diff, all criteria met
- VERDICT: ACCEPT
```

### No Silent Descoping

**PM must NEVER silently drop acceptance criteria.** If a requirement is too large or out of scope:

1. PM must explicitly call out what is being descoped and why
2. PM must create a new `.todo.md` issue for each descoped requirement
3. The descoped items must be traceable — the new issue should reference the original

## Agents

| Agent | File | Role |
|-------|------|------|
| Product Manager | `.claude/agents/product-manager.md` | Grooms issues + final acceptance |
| Software Engineer | `.claude/agents/software-engineer.md` | Implements code + tests |
| Tester | `.claude/agents/tester.md` | Runs tests, verifies acceptance criteria |
| On-Call Engineer | `.claude/agents/oncall-engineer.md` | Monitors CI/CD, fixes pipeline failures |

## Technology Stack

- Language: Python 3.13
- Framework: FastAPI (async)
- Database: PostgreSQL + SQLAlchemy
- Queue/Pub-Sub: Redis
- Package manager: `uv` (run from `backend/` directory)
- Tests: `cd backend && uv run pytest tests/ -v`
- Lint: `cd backend && uv run ruff check`
- Format: `cd backend && uv run ruff format`
- Frontend: React + Vite (in `web/` directory)

## How to Pick Issues

1. List `.groomed.md` files in `docs/tracker/`
2. Pick the lowest-numbered issues first (lower = more foundational)
3. Check dependencies -- don't start until deps are `.done.md`
4. Pick 2 independent issues at a time for parallel implementation

## Task Panel (Claude Code Built-in Tasks)

The orchestrator MUST use the Claude Code task panel to track every step of the pipeline. Tasks are session-scoped progress trackers — they are NOT the same as issues in `docs/tracker/`.

### How Task Panel Items Should Look

Each task panel item tracks a pipeline step for ONE issue:

| Task Subject | Example |
|---|---|
| `[PM groom] issue #01` | PM grooming one issue |
| `[SWE] implement issue #01` | Engineering one issue |
| `[QA] verify issue #01` | Testing one issue |
| `[PM accept] issue #01` | Acceptance + commit one issue |
| `[Pull next] pick 2 issues from backlog` | Pick up more work |

### Pipeline Per Batch (2 issues in parallel)

```
[PM groom #N] -> [SWE #N] -> [QA #N] -> [PM accept #N] --\
                                                           +--> [Pull next]
[PM groom #M] -> [SWE #M] -> [QA #M] -> [PM accept #M] --/
```

Set up blockedBy dependencies. Launch parallel agents (e.g., 2 SWE agents simultaneously).

### Pull Next Work

The last item in every batch is always "[Pull next] pick 2 issues from backlog":
1. Check `docs/tracker/` for `.todo.md` or `.groomed.md` files
2. Pick the 2 lowest-numbered groomed issues (groom first if only .todo.md)
3. Create a new batch of task panel items with dependencies
4. Start the pipeline again

## Conventions

- All backend code in `backend/codehive/`
- All backend tests in `backend/tests/`
- Frontend code in `web/` (React + Vite)
- Every issue must include tests
- Lint with `uv run ruff check`
- Format with `uv run ruff format`
- Commit message: "Implement issue NN: short description"
- Only commit after PM accepts
- Issues are NEVER deleted — they move through statuses
