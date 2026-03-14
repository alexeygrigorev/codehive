# 12: Create Remaining Issues from Specs and Plan

## Description
Read through all project documentation and create `.todo.md` issues for Phases 2-10 and any missing features from the product spec and brainstorm. Each issue should be a focused, implementable unit of work with clear scope, file paths, and dependency references.

## Sources to read
- `docs/product-spec.md` -- full product specification
- `docs/plan.md` -- implementation plan (Phases 2-10)
- `docs/concept-brainstorm.md` -- original brainstorm with additional ideas

## What to create issues for
- Phase 2: Web App (React scaffolding, project dashboard, session view, WebSocket, diff viewer, etc.)
- Phase 3: Sub-agents & orchestration
- Phase 4: Checkpoints, roles, archetypes
- Phase 5: Terminal client (TUI + command mode + rescue)
- Phase 6: Telegram bot
- Phase 7: Claude Code bridge
- Phase 8: GitHub integration (one-way issue import)
- Phase 9: Voice & mobile (PWA)
- Phase 10: SSH & remote execution
- Any features from product-spec.md or concept-brainstorm.md not yet covered

## Rules
- One issue per deliverable -- keep scope small and focused
- Include description, scope (files/modules), and dependencies
- Number issues sequentially starting from 14 (13 is taken by secrets-management)
- Check for overlap with existing issues #01-#11 and #13

## Dependencies
- None (can be done anytime)

## Acceptance Criteria

- [ ] Every deliverable listed in `docs/plan.md` Phases 2-10 is covered by at least one new `.todo.md` file in `docs/tracker/`
- [ ] No new issue overlaps in scope with existing issues #01-#11 or #13 (FastAPI setup, docker-compose infra, DB models, project CRUD, session CRUD, task queue API, event bus, execution layer, engine adapter, session scheduler, CLI session commands, secrets management)
- [ ] Each new issue file follows the established format: title (`# NN: Title`), `## Description`, `## Scope` (with file/module paths), `## Dependencies` (referencing issue numbers)
- [ ] Issues are numbered sequentially starting from 14 with no gaps
- [ ] Issues are small and focused -- each covers a single deliverable or tightly related set of deliverables (not an entire phase in one issue)
- [ ] Phase 2 (Web App) has at minimum 3 separate issues (scaffolding, core session view, WebSocket/realtime)
- [ ] Phase 3 (Sub-Agents) has at minimum 2 separate issues (spawning/orchestration backend, UI tree view)
- [ ] Phases 4-10 each have at least 1 issue
- [ ] Dependencies between issues are correctly specified (e.g., web UI issues depend on API issues from Phase 0-1; sub-agent UI depends on sub-agent backend)
- [ ] All created issue filenames follow the pattern `NN-short-name.todo.md`
- [ ] Features from `docs/product-spec.md` that are not in the plan phases (e.g., pending questions UI, session replay, approval gates, agent modes) are either covered by existing issues or have new issues created
- [ ] A summary list of all created issues (number, title, phase) is logged in this issue's Log section

## Test Scenarios

Since this issue produces documentation files (not code), "tests" are structural validations:

### Structural: File format
- Every new `.todo.md` file in `docs/tracker/` has a `# NN:` title line
- Every new file has a `## Description` section that is non-empty
- Every new file has a `## Scope` section listing at least one file or module path
- Every new file has a `## Dependencies` section (even if "None")

### Coverage: Plan phases
- Count issues tagged/scoped to Phase 2 -- at least 3 exist
- Count issues tagged/scoped to Phase 3 -- at least 2 exist
- Every phase from 4 through 10 has at least 1 issue

### Coverage: No gaps
- Cross-reference every bullet in `docs/plan.md` Phase 2-10 deliverables sections against the created issues -- no deliverable is left uncovered
- Cross-reference key product-spec features (sub-agent visibility, pending questions, checkpoints, agent modes, approval gates) against issue set -- all are covered

### Overlap: No duplicates
- No new issue covers the same scope as issues #01-#11 or #13
- No two new issues cover the same scope as each other

### Dependencies: Correctness
- No issue depends on a non-existent issue number
- Web UI issues depend on backend API issues (directly or transitively)
- Sub-agent UI issue depends on sub-agent backend issue

## Implementation Notes
- The SWE should read all three source documents thoroughly before creating issues
- Use existing issues (#01-#13) as format examples
- Keep each issue implementable in roughly 1-3 focused sessions
- Prefer splitting over lumping -- it is better to have too many small issues than too few large ones
- The concept-brainstorm.md may contain ideas not in the plan -- use judgment about which are worth tracking as issues vs. deferring

## Log

### [SWE] 2026-03-14 17:00
- Read all source documents: product-spec.md, plan.md, concept-brainstorm.md
- Reviewed all existing issues #01-#13 to understand format and avoid overlap
- Created 39 new issue files (#14-#52) covering Phases 2-10 and product-spec features

**Phase 2 - Web App (7 issues):**
- #14: React App Scaffolding (Vite + TypeScript + Tailwind)
- #15: Web Project Dashboard
- #16: Web Session Chat Panel (streaming messages)
- #17: Web Session Sidebar (ToDo, files, timeline, sub-agents)
- #18: WebSocket Client for Real-Time Updates
- #19: Web Diff Viewer Component
- #20: Web Session Mode Switcher and Approval UI

**Phase 3 - Sub-Agents (3 issues):**
- #21: Sub-Agent Spawning Backend (spawn tool, structured reports)
- #22: Orchestrator Mode (no file edits, plan/decompose/monitor)
- #23: Web Sub-Agent Tree View

**Phase 4 - Checkpoints, Roles, Archetypes (3 issues):**
- #24: Checkpoint Creation and Rollback
- #25: Agent Roles (YAML definitions, global + project overrides)
- #26: Project Archetypes

**Phase 5 - Terminal Client (4 issues):**
- #27: TUI Dashboard and Navigation (Textual)
- #28: TUI Session View (chat, todo, timeline, files)
- #29: CLI Command Mode (extended non-interactive commands)
- #30: TUI Rescue Mode

**Phase 6 - Telegram Bot (2 issues):**
- #31: Telegram Bot Commands
- #32: Telegram Push Notifications and Inline Approvals

**Phase 7 - Claude Code Bridge (2 issues):**
- #33: Claude Code CLI Wrapper and Event Parser
- #34: Claude Code Engine Adapter

**Phase 8 - GitHub Integration (2 issues):**
- #35: GitHub Issue Import (one-way sync)
- #36: GitHub Webhook Handler and Auto-Session Trigger

**Phase 9 - Voice & Mobile (3 issues):**
- #37: Voice Input (browser STT + Whisper fallback)
- #38: PWA Manifest, Service Worker, Push Notifications
- #39: Mobile-Optimized Responsive Layouts

**Phase 10 - SSH & Remote (2 issues):**
- #40: SSH Connection Manager
- #41: Tunnel Manager and Preview Links

**Product-spec features not in plan phases (11 issues):**
- #42: Web Pending Questions UI
- #43: Session Replay
- #44: Approval Gates (configurable confirmation for destructive actions)
- #45: Agent Modes Backend Logic (brainstorm, interview, planning, execution, review)
- #46: Issue Tracker API (project-level issues CRUD)
- #47: Workspace Management API
- #48: Project Knowledge Base and Agent Charter
- #49: Filesystem Sandbox and Command Policy
- #50: Secrets Redaction in Logs and Output
- #51: Persistent Session Logs
- #52: Web UI for Checkpoints and Roles

- Files created: 39 new `.todo.md` files in docs/tracker/ (#14 through #52)
- No code changes, no tests needed (documentation-only issue)
- All issues follow established format: title, description, scope with file paths, dependencies
- No overlap with existing issues #01-#11, #13
- All plan.md Phase 2-10 deliverables covered
- Product-spec features (pending questions, session replay, approval gates, agent modes, roles, archetypes, knowledge base, sandbox, secrets redaction) all covered

### [QA] 2026-03-14 17:30
- Tests: N/A (documentation-only issue, no code changes)
- Ruff: N/A
- Acceptance criteria:
  1. Every plan.md Phase 2-10 deliverable covered by .todo.md files: PASS (39 files, #14-#52)
  2. No overlap with existing issues #01-#11, #13: PASS (verified scopes are distinct; #50 vs #13, #29 vs #11 properly differentiated with dependencies)
  3. Format (title, Description, Scope, Dependencies): PASS (all 39 files checked)
  4. Sequential numbering 14-52 with no gaps: PASS
  5. Issues are small and focused: PASS (each covers a single deliverable or tightly related set)
  6. Phase 2 has 3+ issues: PASS (7 issues: #14-#20)
  7. Phase 3 has 2+ issues: PASS (3 issues: #21-#23)
  8. Phases 4-10 each have 1+ issue: PASS (Phase 4: 3, Phase 5: 4, Phase 6: 2, Phase 7: 2, Phase 8: 2, Phase 9: 3, Phase 10: 2)
  9. Dependencies correctly specified: PASS (all refs point to valid issue numbers #01-#46; web UI issues depend on backend; sub-agent UI #23 depends on #21)
  10. Filenames follow NN-short-name.todo.md pattern: PASS
  11. Product-spec features not in plan phases covered: PASS (11 additional issues #42-#52 covering pending questions, session replay, approval gates, agent modes, issue tracker, workspace API, knowledge base, sandbox, secrets redaction, persistent logs, checkpoint/roles UI)
  12. Summary list logged in issue: PASS (SWE log includes full list by phase)
- VERDICT: PASS

### [PM] 2026-03-14 18:00
- Reviewed: 39 new .todo.md files (#14-#52) in docs/tracker/
- Spot-checked 6 files across phases (#14, #21, #31, #40, #45, #49) for format quality
- All have correct structure: # NN: Title, ## Description, ## Scope (with file paths), ## Dependencies
- Phase coverage verified against plan.md:
  - Phase 2: 7 issues (#14-#20) -- all deliverables from 2.5 covered
  - Phase 3: 3 issues (#21-#23) -- all deliverables from 3.5 covered
  - Phase 4: 3 issues (#24-#26) -- all deliverables from 4.5 covered
  - Phase 5: 4 issues (#27-#30) -- all deliverables from 5.4 covered
  - Phase 6: 2 issues (#31-#32) -- all deliverables from 6.3 covered
  - Phase 7: 2 issues (#33-#34) -- all deliverables from 7.3 covered
  - Phase 8: 2 issues (#35-#36) -- all deliverables from 8.4 covered
  - Phase 9: 3 issues (#37-#39) -- all deliverables from 9.3 covered
  - Phase 10: 2 issues (#40-#41) -- all deliverables from 10.3 covered
- Product-spec features: 11 additional issues (#42-#52) covering pending questions UI, session replay, approval gates, agent modes, issue tracker API, workspace API, knowledge base, filesystem sandbox, secrets redaction, persistent logs, checkpoint/roles UI
- Dependency references verified: all point to valid existing issue numbers, web UI depends on backend, sub-agent UI (#23) depends on sub-agent backend (#21)
- No overlap with existing #01-#11, #13 confirmed
- Sequential numbering 14-52 with no gaps confirmed
- Results verified: real data present (39 files exist on disk with correct content)
- Acceptance criteria: all 12 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
