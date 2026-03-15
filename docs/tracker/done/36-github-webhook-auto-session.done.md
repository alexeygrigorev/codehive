# 36: GitHub Webhook Handler and Auto-Session Trigger

## Description
Implement a webhook endpoint that receives GitHub issue events (opened, edited, closed, reopened) and can auto-create codehive sessions for new issues. Support configurable trigger modes: manual, suggest, or auto. The webhook validates the GitHub signature (`X-Hub-Signature-256`), parses the event payload, routes to the appropriate handler, and--depending on the project's trigger mode--imports the issue and optionally creates a session linked to it.

## Scope
- `backend/codehive/integrations/github/webhook.py` -- Webhook receiver: validate HMAC-SHA256 signature, parse payload, route to handler by event type and action
- `backend/codehive/integrations/github/triggers.py` -- Auto-session trigger logic: given an imported issue and a trigger mode, decide whether to create a session and do so if appropriate
- `backend/codehive/api/routes/webhooks.py` -- Webhook endpoint (`POST /api/webhooks/github`) that accepts GitHub webhook deliveries
- `backend/codehive/api/schemas/github.py` -- (modify) add schemas for webhook config and trigger mode
- `backend/codehive/api/routes/github.py` -- (modify) extend the configure endpoint to accept `webhook_secret` and `trigger_mode` fields
- `backend/codehive/config.py` -- (modify if needed) add default webhook secret setting
- `backend/tests/test_github_webhook.py` -- Webhook handling and trigger tests

## Design Details

### Webhook Receiver (`integrations/github/webhook.py`)
- `verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool` -- Computes HMAC-SHA256 of the raw body with the webhook secret and compares to the `X-Hub-Signature-256` header using `hmac.compare_digest`. Returns True/False.
- `parse_webhook_event(headers: dict, body: dict) -> WebhookEvent` -- Extracts the event type from `X-GitHub-Event` header, the action from the body, and returns a dataclass/model with `event_type`, `action`, `payload`.
- Supported events: `issues` with actions `opened`, `edited`, `closed`, `reopened`. All other event types or actions are accepted (200 response) but ignored (no-op).

### Trigger Logic (`integrations/github/triggers.py`)
- `handle_issue_event(db, project, event) -> TriggerResult` -- Main handler:
  1. Import/upsert the issue using the existing `importer.import_issues` logic (or a single-issue variant)
  2. Check `project.github_config["trigger_mode"]` (default: `"manual"`)
  3. If `"manual"`: import only, no session created
  4. If `"suggest"`: import the issue, return a result indicating a session is suggested (but not created). The suggestion is recorded in the result for the caller to act on (e.g., notification in a future issue).
  5. If `"auto"`: import the issue and create a new session linked to it via `core/session.create_session`. Session name is derived from the issue title (e.g., `"GH#{number}: {title}"`, truncated to 255 chars). Engine defaults to `"native"`, mode defaults to `"execution"`, status is `"idle"`.
- `TriggerResult` dataclass: `issue_id: UUID | None`, `session_id: UUID | None`, `action_taken: str` (one of `"imported"`, `"suggested"`, `"session_created"`, `"ignored"`)
- For `closed` action with `trigger_mode=auto`: import/update the issue only, do NOT create a session.
- For `reopened` action with `trigger_mode=auto`: import/update the issue and create a session (same as `opened`).

### Webhook API Endpoint (`api/routes/webhooks.py`)
- `POST /api/webhooks/github` -- Accepts GitHub webhook deliveries.
  - Reads raw request body for signature verification.
  - Looks up the project by matching `github_config.owner` and `github_config.repo` against the `repository.owner.login` and `repository.name` fields in the payload.
  - If no matching project found: returns 404 with `"No project configured for this repository"`.
  - If signature verification fails: returns 401 with `"Invalid signature"`.
  - If signature verification is skipped (no `webhook_secret` configured on the project): log a warning but still process the event.
  - On success: returns 200 with the `TriggerResult` serialized as JSON.

### Configuration Extension (`api/routes/github.py`)
- Extend `GitHubConfigureRequest` to accept two optional fields:
  - `webhook_secret: str | None` -- HMAC secret for webhook signature verification
  - `trigger_mode: str` -- one of `"manual"`, `"suggest"`, `"auto"` (default: `"manual"`)
- These are stored in the `github_config` JSONB alongside the existing `owner`, `repo`, `token` fields.
- Extend `GitHubStatusResponse` to include `trigger_mode`.
- Existing endpoints must continue to work unchanged (backward compatible -- the new fields are optional).

### What is NOT in scope
- Notification delivery for `suggest` mode (future issue -- this issue only records the suggestion in the TriggerResult)
- Periodic/background sync (already deferred from #35)
- Bidirectional sync or PR creation (future per product spec)
- GitHub App installation flow (this uses personal access tokens and manual webhook setup)

## Dependencies
- Depends on: #35 (GitHub issue import) -- DONE. Provides client, mapper, importer, API routes, and `github_config` JSONB column
- Depends on: #05 (Session CRUD API) -- DONE. Provides `core/session.create_session` for auto-session creation

## Acceptance Criteria

- [ ] `POST /api/webhooks/github` with a valid `issues` event payload (`action: opened`) and correct `X-Hub-Signature-256` returns 200 with a JSON body containing `action_taken`
- [ ] `POST /api/webhooks/github` with an invalid signature returns 401
- [ ] `POST /api/webhooks/github` with a payload referencing a repository that has no matching project returns 404
- [ ] `POST /api/webhooks/github` with a non-`issues` event type (e.g., `push`, `pull_request`) returns 200 with `action_taken: "ignored"`
- [ ] `POST /api/webhooks/github` with `issues` event and unsupported action (e.g., `labeled`) returns 200 with `action_taken: "ignored"`
- [ ] With `trigger_mode: "manual"`: webhook imports/upserts the issue but does NOT create a session. `action_taken` is `"imported"`
- [ ] With `trigger_mode: "suggest"`: webhook imports the issue and returns `action_taken: "suggested"` with `session_id: null`
- [ ] With `trigger_mode: "auto"` and `action: "opened"`: webhook imports the issue AND creates a session linked to it. `action_taken` is `"session_created"` and `session_id` is non-null
- [ ] With `trigger_mode: "auto"` and `action: "closed"`: webhook imports/updates the issue but does NOT create a session. `action_taken` is `"imported"`
- [ ] With `trigger_mode: "auto"` and `action: "reopened"`: webhook imports the issue and creates a session. `action_taken` is `"session_created"`
- [ ] Auto-created sessions have `name` derived from the GitHub issue (e.g., `"GH#42: Fix login bug"`), `engine: "native"`, `mode: "execution"`, `status: "idle"`, and `issue_id` set to the imported issue's ID
- [ ] The auto-created session is retrievable via `GET /api/sessions/{id}` and its `issue_id` matches the imported issue
- [ ] `verify_signature` uses HMAC-SHA256 with `hmac.compare_digest` (constant-time comparison) to prevent timing attacks
- [ ] When no `webhook_secret` is configured on the project, signature verification is skipped (event is still processed)
- [ ] `POST /api/projects/{project_id}/github/configure` accepts optional `webhook_secret` and `trigger_mode` fields; existing calls without these fields still work (backward compatible)
- [ ] `GET /api/projects/{project_id}/github/status` includes `trigger_mode` in the response
- [ ] Webhooks router is registered in `create_app()` and the endpoint is accessible
- [ ] `uv run pytest backend/tests/test_github_webhook.py -v` passes with 20+ tests covering all the above

## Test Scenarios

### Unit: Signature verification (`integrations/github/webhook.py`)
- `verify_signature` returns True when the HMAC-SHA256 of the payload matches the `X-Hub-Signature-256` header
- `verify_signature` returns False when the signature does not match (wrong secret)
- `verify_signature` returns False when the signature header is malformed (missing `sha256=` prefix)
- `verify_signature` returns False when the signature header is empty

### Unit: Webhook event parsing (`integrations/github/webhook.py`)
- `parse_webhook_event` extracts event type from `X-GitHub-Event` header and action from body
- `parse_webhook_event` with `issues` event and `opened` action returns correct WebhookEvent
- `parse_webhook_event` with `push` event returns WebhookEvent with event_type `"push"`

### Unit: Trigger logic (`integrations/github/triggers.py`)
- `handle_issue_event` with `trigger_mode: "manual"` imports issue, returns `action_taken: "imported"`, `session_id: None`
- `handle_issue_event` with `trigger_mode: "suggest"` imports issue, returns `action_taken: "suggested"`, `session_id: None`
- `handle_issue_event` with `trigger_mode: "auto"` and `action: "opened"` imports issue and creates session, returns `action_taken: "session_created"` with valid `session_id`
- `handle_issue_event` with `trigger_mode: "auto"` and `action: "closed"` imports issue, returns `action_taken: "imported"`, no session created
- `handle_issue_event` with `trigger_mode: "auto"` and `action: "reopened"` creates a session
- `handle_issue_event` with `trigger_mode: "auto"` and `action: "edited"` imports/updates issue, returns `action_taken: "imported"` (no new session for edits)
- Auto-created session has correct name format, engine, mode, status, and issue_id linkage

### Integration: Webhook API endpoint via AsyncClient
- POST `/api/webhooks/github` with valid signature and `issues/opened` event for a configured project returns 200 with TriggerResult
- POST `/api/webhooks/github` with invalid signature returns 401
- POST `/api/webhooks/github` referencing an unknown repository returns 404
- POST `/api/webhooks/github` with `push` event returns 200 with `action_taken: "ignored"`
- POST `/api/webhooks/github` with `issues/labeled` action returns 200 with `action_taken: "ignored"`
- POST `/api/webhooks/github` with `trigger_mode: "auto"` creates a session retrievable via GET `/api/sessions/{id}`
- POST `/api/webhooks/github` without `webhook_secret` on the project still processes the event (no 401)
- POST `/api/webhooks/github` with `trigger_mode: "manual"` imports issue but no session created (verify via GET sessions for project)

### Integration: Configuration backward compatibility
- POST `/api/projects/{project_id}/github/configure` without `webhook_secret` or `trigger_mode` still works (200, uses defaults)
- POST `/api/projects/{project_id}/github/configure` with `trigger_mode: "auto"` stores it and GET status returns it
- GET `/api/projects/{project_id}/github/status` for a project configured before this change (no `trigger_mode` in JSONB) returns `trigger_mode: "manual"` as default

## Log

### [SWE] 2026-03-15 12:00
- Implemented GitHub webhook handler and auto-session trigger
- Created `integrations/github/webhook.py`: `verify_signature` (HMAC-SHA256 with `hmac.compare_digest`), `parse_webhook_event`, `WebhookEvent` dataclass
- Created `integrations/github/triggers.py`: `handle_issue_event` with manual/suggest/auto trigger modes, `TriggerResult` dataclass, single-issue upsert logic
- Created `api/routes/webhooks.py`: `POST /api/webhooks/github` endpoint with project lookup by repo owner/name, signature verification, event routing
- Modified `api/schemas/github.py`: added `webhook_secret` and `trigger_mode` fields to `GitHubConfigureRequest`, added `trigger_mode` to `GitHubStatusResponse`
- Modified `api/routes/github.py`: extended configure endpoint to store `webhook_secret` and `trigger_mode` in JSONB, extended status endpoint to return `trigger_mode`
- Modified `api/app.py`: registered `webhooks_router` in `create_app()`
- Files modified: `backend/codehive/integrations/github/webhook.py` (new), `backend/codehive/integrations/github/triggers.py` (new), `backend/codehive/api/routes/webhooks.py` (new), `backend/codehive/api/schemas/github.py`, `backend/codehive/api/routes/github.py`, `backend/codehive/api/app.py`
- Tests added: 30 tests in `backend/tests/test_github_webhook.py` covering signature verification (4), event parsing (3), trigger logic (7), webhook API endpoint (11), configuration backward compatibility (4), router registration (1)
- Build results: 965 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 12:30
- Tests: 30 passed, 0 failed (test_github_webhook.py); 965 passed full suite
- Ruff check: clean
- Ruff format: clean (7 files already formatted)
- Acceptance criteria:
  1. POST /api/webhooks/github with valid issues/opened + correct signature returns 200 with action_taken: PASS
  2. Invalid signature returns 401: PASS
  3. Unknown repo returns 404: PASS
  4. Non-issues event (push) returns 200 with action_taken "ignored": PASS
  5. Unsupported action (labeled) returns 200 with action_taken "ignored": PASS
  6. trigger_mode "manual" imports only, no session: PASS
  7. trigger_mode "suggest" returns "suggested", session_id null: PASS
  8. trigger_mode "auto" + opened creates session: PASS
  9. trigger_mode "auto" + closed imports only, no session: PASS
  10. trigger_mode "auto" + reopened creates session: PASS
  11. Auto-created session has correct name/engine/mode/status/issue_id: PASS
  12. Auto-created session retrievable via GET /api/sessions/{id}: PASS
  13. verify_signature uses HMAC-SHA256 with hmac.compare_digest: PASS
  14. No webhook_secret configured skips verification, still processes: PASS
  15. Configure accepts optional webhook_secret and trigger_mode, backward compatible: PASS
  16. GET status includes trigger_mode: PASS
  17. Webhooks router registered in create_app(): PASS
  18. 20+ tests covering all criteria (30 tests): PASS
- VERDICT: PASS

### [PM] 2026-03-15 13:00
- Reviewed diff: 7 files changed (3 new, 4 modified) plus 1 new test file
- New files: `integrations/github/webhook.py` (57 lines), `integrations/github/triggers.py` (141 lines), `api/routes/webhooks.py` (106 lines)
- Modified files: `api/schemas/github.py` (+3 lines), `api/routes/github.py` (+5 lines), `api/app.py` (+2 lines)
- Tests: `tests/test_github_webhook.py` (537 lines, 30 tests) -- all 30 pass, confirmed locally
- Results verified: real test execution confirmed (30 passed in 1.86s), all integration tests exercise actual HTTP endpoints with DB persistence
- Code quality: clean separation of concerns (webhook receiver, trigger logic, API route), constant-time HMAC comparison, proper async/await, follows existing project patterns
- Acceptance criteria: all 18/18 met
  1. Valid issues/opened with correct signature returns 200 with action_taken: MET
  2. Invalid signature returns 401: MET
  3. Unknown repo returns 404: MET
  4. Non-issues event returns 200 with "ignored": MET
  5. Unsupported action returns 200 with "ignored": MET
  6. trigger_mode "manual" imports only: MET
  7. trigger_mode "suggest" returns "suggested", session_id null: MET
  8. trigger_mode "auto" + opened creates session: MET
  9. trigger_mode "auto" + closed imports only: MET
  10. trigger_mode "auto" + reopened creates session: MET
  11. Auto-session has correct name/engine/mode/status/issue_id: MET
  12. Auto-session retrievable via GET /api/sessions/{id}: MET
  13. verify_signature uses HMAC-SHA256 with hmac.compare_digest: MET
  14. No webhook_secret skips verification, still processes: MET
  15. Configure accepts optional webhook_secret and trigger_mode, backward compatible: MET
  16. GET status includes trigger_mode: MET
  17. Webhooks router registered in create_app(): MET
  18. 20+ tests (30 tests): MET
- Follow-up issues created: none
- VERDICT: ACCEPT
