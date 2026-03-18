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

### Responsibility Model

**Every role owns their deliverable.** Quality is not centralized — it is distributed across the team. Each agent is accountable for the quality of their specific output:

| Role | Owns | Accountable For |
|------|------|----------------|
| PM | The whole application — UX, functionality, quality | Ensuring the feature actually works as the user expects. The PM is the user's last line of defense. If PM says "accepted" and the user finds it broken, that's a PM failure. |
| SWE | Code correctness, tests | Writing code that works and tests that prove it. If QA finds bugs, that's an SWE failure. |
| QA/Tester | Verification, evidence | Providing proof that things work — not claims. If QA says "passed" without running the test, that's a QA failure. |
| Orchestrator | The team | Managing the pipeline and verifying that each agent did their job properly. If any agent cuts corners and the orchestrator accepts it, that's an orchestrator failure. |

**The PM owns the user experience.** The PM is the user's advocate. When accepting a deliverable, the PM must verify that the feature works from the user's perspective — not just that code was written and tests pass. The PM should:
- Verify the actual UI/UX matches what the user asked for
- Check screenshots, test output, and logs — not just agent claims
- Reject if the deliverable doesn't meet the user's expectations
- Think "if the user checks this right now, will they be satisfied?"

**The Orchestrator manages the team.** The orchestrator doesn't own quality directly — the PM does. But the orchestrator is responsible for ensuring the PM (and every other agent) does their job properly. If the PM rubber-stamps something, the orchestrator must catch it and send it back. The orchestrator:
- Verifies agent results against acceptance criteria before accepting
- Questions suspicious results (too fast, missing evidence, contradicts user feedback)
- Sends agents back with specific feedback when their work is insufficient
- Never forwards an agent's claim without critical evaluation

### False Confidence is the Worst Outcome

The single worst thing the orchestrator can do is tell the user "it works" when it doesn't. This destroys trust. When the user checks and finds it broken, they lose confidence in the entire pipeline — and rightfully so.

**Rules to prevent false confidence:**

1. **Never say "it works" unless you have firsthand evidence.** An agent saying "passed" is not firsthand evidence. Actual test output showing real data, screenshots showing real UI, logs showing real requests — that is evidence.
2. **If you're not sure, say you're not sure.** "The agent reports it passed but I haven't independently verified" is always better than "it works." Honesty about uncertainty is valued. False certainty is not.
3. **If something contradicts user experience, the user is right.** The user is testing the real app. If they say it's broken, it's broken — regardless of what any test or agent claims. Investigate why the test passed when the feature is broken.
4. **Treat every "it works" claim as a promise.** Before making that promise, ask yourself: "If the user checks right now, will it actually work?" If you can't answer yes with evidence, don't make the claim.

**NEVER wait for user input.** The pipeline runs autonomously. If something needs user action (e.g. configuring a secret, testing on their machine, confirming a deployment), note it in the issue file as a "USER ACTION REQUIRED" item and keep moving to the next issue. Do not stop the pipeline.

**NEVER block on dependencies within a batch.** If issue A is groomed but issue B is still grooming, launch the SWE agent for A immediately. Don't wait for B. Each issue's pipeline is independent — launch agents as soon as their predecessor step completes, regardless of the other issue in the batch.

**Always have a "Pull next" task.** The pipeline never stops. After committing a batch, immediately pick the next 2 issues and continue.

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

### Definition of Groomed

A `.groomed.md` issue must contain the following before an engineer can pick it up:

#### User Stories (required)

Every feature must have concrete user stories that describe **what a real user does step by step**. These are NOT abstract requirements — they are specific, realistic scenarios written from the user's perspective.

Bad (too abstract):
```
- [ ] Page loads correctly
- [ ] User can create a project
```

Good (concrete user story):
```
### Story: Developer creates a project from their local codebase
1. User opens the dashboard at /
2. User clicks "New Project"
3. User clicks "Empty Project"
4. User types "/home/user/git/myapp" in the directory path field
5. The name field auto-fills with "myapp"
6. User clicks "Create Project"
7. User is redirected to the project page showing "myapp" as the title
8. The sidebar shows "myapp" in the project list
```

Each story must be:
- **Specific** — exact clicks, exact fields, exact expected results
- **Realistic** — based on how a real developer would use the feature
- **Testable** — can be directly translated into a Playwright e2e test
- **End-to-end** — covers the full flow from user action to visible result

#### E2E Test Scenarios (required for UI features)

The PM must define which user stories become Playwright e2e tests. Each scenario maps 1:1 to a user story and specifies:
- Preconditions (what state the app must be in)
- Steps (user actions)
- Assertions (what the user should see)

These scenarios are the **contract between PM and SWE** — the SWE implements them as actual Playwright tests, and QA verifies they pass.

#### Acceptance Criteria Checklist (required)

Concrete, checkable items. Each criterion must be verifiable by running the app or running a test — not by reading code.

### Definition of Done

"Done" has a specific meaning at each stage. Each role has concrete checkboxes.

#### SWE Done

- [ ] Code written and follows existing patterns
- [ ] Unit tests written and passing — **actual `pytest`/`vitest` output included in log**
- [ ] Lint clean — `ruff check` and `tsc --noEmit` output shown
- [ ] **E2e tests written** from the PM's scenarios (for any UI feature)
- [ ] **E2e tests actually run** against real app (backend + frontend started, Playwright executed) — **actual Playwright output included in log**
- [ ] If e2e tests could not be run: explicitly state "NOT RUN — reason" (never silently skip)
- [ ] **Screenshots taken** via Playwright for UI features — saved to `/tmp/` and paths listed in log
- [ ] The app starts without errors after changes
- [ ] **Bug fixes: TDD approach** — write a test that reproduces the bug FIRST, confirm it FAILS, then fix, confirm it PASSES. Include both failing and passing output in log.
- [ ] Log entry appended to issue file with all evidence

"It compiles" is NOT done. "I ran the app, ran the e2e tests, and here's the Playwright output and screenshots" IS done.

#### QA Done

- [ ] Read all user stories from the groomed spec
- [ ] **Run every e2e test** that the SWE wrote — show full Playwright output
- [ ] **View every screenshot** the SWE took — describe what you see, flag any issues
- [ ] If any e2e test was marked "NOT RUN" by SWE: **run it now** or explain why it can't run
- [ ] Run unit tests — show actual output with counts
- [ ] Run lint — show actual output
- [ ] **Walk through each user story manually** via Playwright: start the app, follow the steps, take screenshots at each step, verify the expected result
- [ ] Each acceptance criterion marked PASS/FAIL with evidence (screenshot path, test output line, log excerpt)
- [ ] All evidence attached to issue log
- [ ] Any suspicious results investigated and explained

"I read the diff and it looks right" is NOT done. "I ran every test, walked through every user story, took screenshots at each step, and here's the evidence" IS done.

#### PM Done

- [ ] Review QA's evidence — **look at every screenshot**, read every test output
- [ ] Verify each user story has a corresponding e2e test that passed
- [ ] Verify each user story's expected result matches the screenshot evidence
- [ ] **Walk through the feature from the user's perspective**: would the user be satisfied?
- [ ] Check for edge cases the stories might have missed
- [ ] No scope silently dropped — any descoped items tracked as new issues
- [ ] If the user reported a bug: verify the fix by checking the specific scenario the user described
- [ ] Verdict: "If the user checks this right now, they will be satisfied" — yes or no?

"QA said it passed" is NOT done. "I reviewed every screenshot, verified every user story matches the evidence, and I guarantee the user will be satisfied" IS done.

#### Orchestrator Done

- [ ] PM provided a concrete verdict with evidence references (not just "ACCEPTED")
- [ ] PM's evidence actually matches the acceptance criteria (orchestrator spot-checks)
- [ ] No contradictions with user feedback (if user said "it's broken", evidence shows it's fixed)
- [ ] All user stories have corresponding e2e tests that were actually run
- [ ] Commit only after all boxes checked

#### Issue Done = All Four

An issue moves to `.done.md` ONLY when:
1. SWE built it and ran e2e tests with evidence
2. QA verified every user story with screenshots and test output
3. PM reviewed evidence and guarantees user satisfaction
4. Orchestrator verified the PM did their job

If any layer skipped their verification, the issue is NOT done.

### Orchestrator Must Verify Agent Results

When a QA or PM agent reports back, the orchestrator MUST NOT rubber-stamp the result. Before accepting:

1. **Re-read the issue's acceptance criteria line by line**
2. **Check each criterion against the agent's report** — did the agent actually address it, or just say "tests pass"?
3. **Reject and re-launch if any criterion was skipped** — with specific instructions about what was missed

Common failures to watch for:
- AC says "run e2e test" → agent wrote the test file but never ran it. **REJECT.**
- AC says "verify visually with screenshots" → agent only did grep checks. **REJECT.**
- AC says "streaming works" → agent checked that code compiles. **REJECT.**
- AC says "no white backgrounds in dark mode" → agent ran unit tests. **REJECT.**

"Tests pass" is NEVER sufficient if the AC requires runtime or visual verification. The orchestrator is the last line of defense — if it doesn't enforce the AC, nobody will.

**Sanity-check agent claims.** If an agent reports success but the result seems too fast, too easy, or contradicts user feedback — question it. Ask for evidence: logs, screenshots, actual output content. A 3-second "LLM roundtrip" is a red flag. A "visual QA passed" with no screenshots is a red flag. Don't forward "passed" without critical thinking.

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
