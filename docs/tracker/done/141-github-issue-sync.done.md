# 141 -- GitHub Issue Sync: Pipeline Progress to GitHub Comments

## Problem

Codehive can import GitHub issues (#35) and auto-create sessions from webhooks (#36), and it can close issues after auto-solve (#54b). But there is no visibility in GitHub of what is happening inside Codehive's pipeline. A developer who files a GitHub issue has no way to know whether Codehive picked it up, what stage it is in, or why it failed -- unless they open the Codehive UI.

Additionally, the current import is coarse: every issue from the repo is imported. There is no way to configure which labels trigger a sync (e.g., only `codehive` or `auto-solve` labeled issues).

## Vision

- When Codehive's pipeline processes a GitHub-originated issue, each stage transition posts a comment on the GitHub issue (e.g., "Grooming started", "Implementation complete -- running tests", "QA passed", "Done -- commit abc123").
- Label-based filtering: projects can configure which GitHub labels trigger import/sync, so not every issue floods the backlog.
- Task completion updates the GitHub issue (already handled by closer.py for auto-solve, but not for the general orchestrator pipeline).

## Scope

### New files
- `backend/codehive/integrations/github/commenter.py` -- Post pipeline status comments on GitHub issues
- `backend/tests/test_github_commenter.py` -- Tests for the commenter module

### Modified files
- `backend/codehive/core/orchestrator_service.py` -- After each pipeline transition, call the commenter if the task's issue has a `github_issue_id`
- `backend/codehive/integrations/github/triggers.py` -- Apply label filter before importing
- `backend/codehive/integrations/github/importer.py` -- Apply label filter during bulk import
- `backend/codehive/api/routes/github.py` -- Extend configure endpoint to accept `sync_labels` field
- `backend/codehive/api/schemas/github.py` -- Add `sync_labels` to configure request/status response

### NOT in scope
- Bidirectional status sync (updating Codehive issue status from GitHub label changes)
- PR creation from Codehive sessions
- Webhook retry/delivery tracking
- GitHub App installation flow (stays with PAT + manual webhook setup)
- Changing the existing auto-solve close behavior (closer.py remains as-is for solver-initiated closes)

## Dependencies
- #35 (GitHub issue import) -- DONE
- #36 (GitHub webhook + auto-session) -- DONE
- #54a (GitHub solver orchestration) -- DONE
- #54b (GitHub issue close) -- DONE
- #22 (Orchestrator mode) -- DONE

## User Stories

### Story: Developer sees pipeline progress on their GitHub issue
1. Developer creates an issue on GitHub in a repo connected to a Codehive project
2. The issue has the label `codehive` (which is in the project's `sync_labels` config)
3. Codehive's webhook receives the event and imports the issue into the backlog
4. A comment appears on the GitHub issue: "Imported into Codehive backlog."
5. When the orchestrator picks up the task and begins grooming, a comment appears: "Pipeline: grooming started."
6. When grooming completes and implementation begins: "Pipeline: implementation started."
7. When tests run: "Pipeline: testing started."
8. When QA passes and PM accepts: "Pipeline: accepted. Commit: abc1234."
9. The developer can follow the entire lifecycle without leaving GitHub

### Story: Developer configures label filtering for a project
1. User opens the Codehive API (or future UI) and calls `POST /api/projects/{id}/github/configure` with `sync_labels: ["codehive", "auto-solve"]`
2. A GitHub issue without any of those labels is created in the repo
3. The webhook fires, but Codehive ignores the issue (not imported, returns `action_taken: "filtered"`)
4. Another issue with the `codehive` label is created
5. This issue IS imported into Codehive's backlog
6. If `sync_labels` is empty or not set, ALL issues are imported (backward compatible)

### Story: Bulk import respects label filter
1. User has configured `sync_labels: ["codehive"]` on a project
2. User triggers `POST /api/projects/{id}/github/import`
3. Only GitHub issues that have at least one of the configured labels are imported
4. Issues without matching labels are skipped
5. The import response shows correct created/updated counts (only for filtered issues)

## Acceptance Criteria

- [ ] New module `backend/codehive/integrations/github/commenter.py` exists with a function `post_pipeline_comment(owner, repo, issue_number, token, message) -> None` that POSTs a comment to the GitHub issue
- [ ] `post_pipeline_comment` raises `GitHubAPIError` on non-2xx responses
- [ ] `post_pipeline_comment` is called by the orchestrator service on each pipeline transition (grooming, implementing, testing, accepting, done) for tasks whose linked issue has a `github_issue_id`
- [ ] Comments include the pipeline step name and a human-readable message (e.g., "Pipeline: grooming started", "Pipeline: done. Commit: abc1234")
- [ ] When transitioning to `done`, the comment includes the git commit SHA if available
- [ ] If `post_pipeline_comment` fails (e.g., network error, invalid token), the pipeline does NOT fail -- the error is logged and the pipeline continues
- [ ] `POST /api/projects/{id}/github/configure` accepts an optional `sync_labels: list[str]` field (default: empty list, meaning sync all)
- [ ] `GET /api/projects/{id}/github/status` returns the configured `sync_labels` list
- [ ] Webhook handler (`handle_issue_event`) checks the incoming issue's labels against the project's `sync_labels` config. If `sync_labels` is non-empty and the issue has none of the configured labels, the event is ignored with `action_taken: "filtered"`
- [ ] Webhook handler with empty `sync_labels` (or no `sync_labels` key) imports all issues as before (backward compatible)
- [ ] `import_issues` bulk import respects `sync_labels` -- only issues with at least one matching label are imported (when `sync_labels` is non-empty)
- [ ] Existing tests for #35 and #36 still pass (no regressions)
- [ ] `uv run pytest backend/tests/test_github_commenter.py -v` passes with 15+ tests
- [ ] `uv run ruff check backend/` is clean
- [ ] `uv run pytest backend/tests/ -v` full suite passes with no regressions

## Technical Notes

### Commenter module (`integrations/github/commenter.py`)
- Follow the same httpx pattern as `closer.py` -- use `_headers(token)` from `client.py`
- `async def post_pipeline_comment(owner: str, repo: str, issue_number: int, token: str, message: str) -> None`
- POST to `https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments` with `{"body": message}`
- Raise `GitHubAPIError` on non-2xx

### Orchestrator integration
- In `OrchestratorService._run_task_pipeline`, after each `pipeline_transition` call, look up the task's linked issue. If the issue has `github_issue_id`, fetch the project's `github_config` and call `post_pipeline_comment`.
- Wrap the call in try/except to prevent pipeline failure on comment posting errors.
- Build message strings in a helper function `build_pipeline_message(step: str, commit_sha: str | None = None) -> str` inside commenter.py.
- Message format examples:
  - `"[Codehive] Pipeline: grooming started."`
  - `"[Codehive] Pipeline: implementation started."`
  - `"[Codehive] Pipeline: testing started."`
  - `"[Codehive] Pipeline: accepted. Commit: abc1234."`
  - `"[Codehive] Pipeline: done."`

### Label filtering
- `github_config` JSONB already stores arbitrary keys. Add `sync_labels: list[str]` (default `[]`).
- In `triggers.py`, before calling `_upsert_issue`, check `config.get("sync_labels", [])`. If non-empty, extract labels from the webhook payload (`event.payload["issue"]["labels"]`) and check if any label name matches. If no match, return `TriggerResult(action_taken="filtered")`.
- In `importer.py`, when iterating over fetched GitHub issues, skip any issue whose labels do not intersect with `sync_labels` (when `sync_labels` is non-empty).
- No migration needed -- `github_config` is already JSONB and accepts arbitrary keys.

### Resolving task -> issue -> github_issue_id chain
- `Task` -> `Task.session_id` -> `Session` -> `Session.issue_id` -> `Issue` -> `Issue.github_issue_id`
- `Issue.project_id` -> `Project` -> `Project.github_config` (for owner, repo, token)
- This chain is already partially followed in `_run_task_pipeline` and `_try_git_commit`. Extract a helper to avoid duplication.

## Test Scenarios

### Unit: Commenter (`integrations/github/commenter.py`)
- `post_pipeline_comment` POSTs to the correct GitHub API URL with the correct body
- `post_pipeline_comment` raises `GitHubAPIError` on 401 response
- `post_pipeline_comment` raises `GitHubAPIError` on 404 response
- `post_pipeline_comment` succeeds on 201 response (no exception)
- `build_pipeline_message("grooming")` returns `"[Codehive] Pipeline: grooming started."`
- `build_pipeline_message("done", commit_sha="abc1234")` returns `"[Codehive] Pipeline: done. Commit: abc1234."`
- `build_pipeline_message("implementing")` returns `"[Codehive] Pipeline: implementation started."`

### Unit: Label filtering in triggers
- `handle_issue_event` with `sync_labels: ["codehive"]` and issue with label `codehive` imports the issue (not filtered)
- `handle_issue_event` with `sync_labels: ["codehive"]` and issue with labels `["bug", "enhancement"]` returns `action_taken: "filtered"`, no issue created
- `handle_issue_event` with `sync_labels: []` (empty) and any issue imports it (backward compatible)
- `handle_issue_event` with no `sync_labels` key in config imports all issues (backward compatible)
- `handle_issue_event` with `sync_labels: ["codehive", "auto-solve"]` and issue with label `auto-solve` imports the issue

### Unit: Label filtering in importer
- `import_issues` with `sync_labels: ["codehive"]` skips issues without matching labels
- `import_issues` with `sync_labels: ["codehive"]` imports issues with matching labels
- `import_issues` with `sync_labels: []` imports all issues (backward compatible)

### Unit: Orchestrator pipeline comment posting
- After pipeline transition to "grooming", commenter is called with correct message (mock commenter)
- After pipeline transition to "done", commenter is called with commit SHA in message (mock commenter)
- If commenter raises an exception, the pipeline continues (error is logged, not re-raised)
- For a task whose issue has no `github_issue_id`, commenter is NOT called
- For a task with no linked issue, commenter is NOT called

### Integration: API configuration
- `POST /api/projects/{id}/github/configure` with `sync_labels: ["codehive"]` stores it in github_config
- `GET /api/projects/{id}/github/status` returns `sync_labels: ["codehive"]` after configuration
- `POST /api/projects/{id}/github/configure` without `sync_labels` still works (backward compatible, defaults to `[]`)
- Existing configure/status/import tests still pass (no regressions)

### Integration: Webhook with label filter
- `POST /api/webhooks/github` with `sync_labels: ["codehive"]` configured and issue with label `codehive` returns `action_taken: "imported"` (or `"session_created"` in auto mode)
- `POST /api/webhooks/github` with `sync_labels: ["codehive"]` configured and issue without `codehive` label returns `action_taken: "filtered"`
- `POST /api/webhooks/github` with no `sync_labels` configured imports all issues as before

## Log

### [SWE] 2026-03-28 10:00
- Implemented all acceptance criteria for issue #141
- Created `backend/codehive/integrations/github/commenter.py` with `post_pipeline_comment()` and `build_pipeline_message()` functions
- Hooked commenter into `OrchestratorService._run_task_pipeline()` -- posts GitHub comment after each pipeline transition (grooming, implementing, testing, accepting, done)
- Added `_try_post_github_comment()` helper to OrchestratorService that resolves Task -> Session -> Issue -> Project chain and posts comment; errors are caught and logged (non-fatal)
- Updated `_try_git_commit()` to return commit SHA so it can be included in the "done" comment
- Added label filtering to `triggers.py` via `_issue_matches_labels()` helper and new `sync_labels` kwarg on `handle_issue_event()`
- Added label filtering to `importer.py` via `sync_labels` kwarg on `import_issues()`
- Extended `GitHubConfigureRequest` schema with `sync_labels: list[str]` field (default: [])
- Extended `GitHubStatusResponse` schema with `sync_labels: list[str]` field
- Updated configure endpoint to store `sync_labels` in github_config JSONB
- Updated status endpoint to return `sync_labels` from config
- Updated import endpoint to pass `sync_labels` to `import_issues()`
- Updated webhook route to pass `sync_labels` to `handle_issue_event()`
- Files modified:
  - `backend/codehive/integrations/github/commenter.py` (NEW)
  - `backend/codehive/integrations/github/triggers.py`
  - `backend/codehive/integrations/github/importer.py`
  - `backend/codehive/core/orchestrator_service.py`
  - `backend/codehive/api/routes/github.py`
  - `backend/codehive/api/routes/webhooks.py`
  - `backend/codehive/api/schemas/github.py`
- Tests added: 36 new tests in `backend/tests/test_github_commenter.py`
  - 7 unit tests for `build_pipeline_message`
  - 4 unit tests for `post_pipeline_comment` (correct URL, 401, 404, 201)
  - 5 unit tests for `_issue_matches_labels` helper
  - 5 unit tests for label filtering in triggers
  - 3 unit tests for label filtering in importer
  - 5 unit tests for orchestrator commenter integration (grooming, done+SHA, failure non-fatal, no github_issue_id, no linked issue)
  - 3 integration tests for API config with sync_labels
  - 4 integration tests for webhook with label filter
- Build results: 2362 tests pass, 0 fail, 3 skipped, ruff clean (1 pre-existing warning in unrelated file)
- Known limitations: none

### [QA] 2026-03-28 10:30
- Tests: 36 passed in test_github_commenter.py, 0 failed
- Full suite: 2362 passed, 3 skipped, 0 failed (no regressions)
- Ruff check: clean (All checks passed!)
- Ruff format: clean (291 files already formatted)
- Acceptance criteria:
  - [PASS] `commenter.py` exists with `post_pipeline_comment(owner, repo, issue_number, token, message) -> None`
  - [PASS] `post_pipeline_comment` raises `GitHubAPIError` on non-2xx (tests for 401, 404)
  - [PASS] `post_pipeline_comment` called by orchestrator on each pipeline transition via `_try_post_github_comment` (called after step transitions and after done transition in `_run_task_pipeline`)
  - [PASS] Comments include step name and human-readable message (e.g., "[Codehive] Pipeline: grooming started.", "[Codehive] Pipeline: implementation started.")
  - [PASS] "done" comments include git commit SHA when available (test_comment_with_commit_sha_on_done)
  - [PASS] Commenter errors are non-fatal -- caught in try/except, logged, pipeline continues (test_commenter_failure_does_not_break_pipeline)
  - [PASS] `POST .../github/configure` accepts optional `sync_labels: list[str]` (default: [])
  - [PASS] `GET .../github/status` returns configured `sync_labels`
  - [PASS] Webhook handler filters by `sync_labels` -- returns `action_taken: "filtered"` when no label match
  - [PASS] Empty `sync_labels` imports all issues (backward compatible) -- tested in triggers, importer, and webhook integration
  - [PASS] `import_issues` bulk import respects `sync_labels` filtering
  - [PASS] Existing tests still pass (2362 total, no regressions)
  - [PASS] 36 tests in test_github_commenter.py (exceeds 15+ requirement)
  - [PASS] `ruff check` is clean
  - [PASS] Full suite passes
- VERDICT: PASS

### [PM] 2026-03-28 11:00
- Reviewed diff: 8 files changed (6 modified, 2 new), 98 insertions, 8 deletions in backend
- Results verified: real data present -- 36 tests exercise commenter, label filtering, orchestrator integration, API config, and webhook end-to-end
- Acceptance criteria: all 15 met
  - commenter.py: correct signature, raises GitHubAPIError on non-2xx, follows httpx pattern from closer.py
  - orchestrator: _try_post_github_comment called after every pipeline transition (line 354 for step entry, line 417 for route result); commit SHA passed on done (lines 412-417); wrapped in try/except (lines 428-458) so errors are non-fatal
  - label filtering: _issue_matches_labels helper in triggers.py with set intersection; backward compatible (empty list matches all); applied in both triggers.py and importer.py
  - API: sync_labels field added to GitHubConfigureRequest (default []) and GitHubStatusResponse; stored in JSONB github_config; passed through configure, status, import, and webhook routes
  - tests: 36 new tests covering unit (message building, HTTP calls, label matching), integration (API config round-trip, webhook filtering with manual and auto modes)
  - full suite: 2362 pass, ruff clean
- Code quality: clean, follows existing patterns, no over-engineering, no unnecessary abstractions
- Follow-up issues created: none needed
- VERDICT: ACCEPT
