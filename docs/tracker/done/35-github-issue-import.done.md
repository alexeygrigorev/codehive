# 35: GitHub Issue Import (One-Way Sync)

## Description
Implement one-way import of GitHub Issues into codehive's internal issue tracker. Users configure a GitHub repo and personal access token per project, then trigger a manual import or let a periodic background task sync issues. GitHub labels and state are mapped to internal issue fields. Already-imported issues (tracked via `github_issue_id` on the Issue model) are updated rather than duplicated.

## Scope
- `backend/codehive/integrations/__init__.py` -- package init
- `backend/codehive/integrations/github/__init__.py` -- package init
- `backend/codehive/integrations/github/client.py` -- GitHub API client (httpx-based) for fetching issues from a repo
- `backend/codehive/integrations/github/mapper.py` -- Map GitHub issue fields (state, labels, assignees, body) to internal Issue fields (status, title, description)
- `backend/codehive/integrations/github/importer.py` -- Import orchestration: fetch GitHub issues, upsert into internal tracker via `core/issues.py`
- `backend/codehive/api/schemas/github.py` -- Pydantic schemas for GitHub config and import endpoints
- `backend/codehive/api/routes/github.py` -- API endpoints: configure GitHub integration per project, trigger manual import, get sync status
- `backend/codehive/config.py` -- (modify) add optional default GitHub token setting
- `backend/codehive/db/models.py` -- (modify) add `GitHubConfig` model or JSONB column on Project for storing repo owner/name/token per project
- `backend/tests/test_github_import.py` -- Unit and integration tests

## Design Details

### GitHub Client (`integrations/github/client.py`)
- Uses `httpx.AsyncClient` to call the GitHub REST API v3
- `list_issues(owner, repo, token, state="all", since=None) -> list[dict]` -- fetches issues (not PRs) from `GET /repos/{owner}/{repo}/issues`, handles pagination
- `get_issue(owner, repo, number, token) -> dict` -- fetches a single issue
- Must filter out pull requests (GitHub's issues endpoint includes PRs; filter by absence of `pull_request` key)
- Raises a custom `GitHubAPIError` on non-200 responses with status code and message

### Mapper (`integrations/github/mapper.py`)
- `map_github_issue(gh_issue: dict) -> dict` -- returns a dict with keys: `title`, `description`, `status`, `github_issue_id`
- GitHub state mapping: `"open"` -> `"open"`, `"closed"` -> `"closed"`
- `title` = GitHub issue title (truncated to 500 chars if needed)
- `description` = GitHub issue body (may be None)
- `github_issue_id` = GitHub issue `number` (int)
- Labels are appended as a tag line at the end of description: `"\n\nLabels: bug, enhancement"` (if any)

### Importer (`integrations/github/importer.py`)
- `import_issues(db, project_id, owner, repo, token, since=None) -> ImportResult`
- For each GitHub issue:
  - If an internal Issue with the same `github_issue_id` and `project_id` already exists: update title/description/status
  - If not: create a new internal Issue via `core/issues.py` with `github_issue_id` set
- Returns an `ImportResult` dataclass: `created: int`, `updated: int`, `errors: list[str]`
- `since` parameter (optional ISO datetime string) filters to issues updated after that time, for incremental sync

### API Endpoints (`api/routes/github.py`)
- `POST /api/projects/{project_id}/github/configure` -- save GitHub repo config (owner, repo, token) for a project. Request body: `{"owner": "...", "repo": "...", "token": "..."}`. Returns 200 with saved config (token masked). Returns 404 if project not found.
- `POST /api/projects/{project_id}/github/import` -- trigger a manual import. Optional request body: `{"since": "2025-01-01T00:00:00Z"}`. Returns 200 with `ImportResult` (created, updated, errors). Returns 404 if project not found. Returns 400 if GitHub config is not set for the project.
- `GET /api/projects/{project_id}/github/status` -- return the saved GitHub config (token masked) and last import timestamp. Returns 404 if project not found. Returns 200 with `{"configured": false}` if no config set.

### Storage for GitHub Config
Add a `github_config` JSONB column (nullable) on the `Project` model to store `{"owner": "...", "repo": "...", "token": "...", "last_import_at": "..."}`. This avoids a new table for MVP. The token is stored as-is in the DB (encryption is out of scope for this issue; secrets management is handled by #13).

### What is NOT in scope
- Webhook listener for real-time push from GitHub (that is #36)
- Auto-session creation from imported issues (that is #36)
- Bidirectional sync (future, per product spec)
- Periodic background sync (can be a follow-up; this issue provides the manual import that a cron/scheduler would call)

## Dependencies
- #46 (issue tracker API) -- DONE. Provides `core/issues.py` with create/update/list and the Issue model with `github_issue_id`
- #04 (project CRUD) -- DONE. Projects must exist; provides Project model
- #03 (database models) -- DONE. Issue model with `github_issue_id` column already exists
- #13 (secrets management) -- DONE. Token storage patterns available

## Acceptance Criteria

- [ ] `POST /api/projects/{project_id}/github/configure` with `{"owner": "octocat", "repo": "Hello-World", "token": "ghp_xxx"}` returns 200 with config where the token is masked (e.g., `"ghp_***"`)
- [ ] `POST /api/projects/{project_id}/github/configure` with a non-existent project_id returns 404
- [ ] `GET /api/projects/{project_id}/github/status` returns 200 with `{"configured": true, "owner": "...", "repo": "...", "token_masked": "ghp_***", "last_import_at": null}` after configure
- [ ] `GET /api/projects/{project_id}/github/status` returns 200 with `{"configured": false}` when no config is set
- [ ] `POST /api/projects/{project_id}/github/import` returns 200 with `{"created": N, "updated": M, "errors": []}` after a successful import
- [ ] `POST /api/projects/{project_id}/github/import` returns 400 when GitHub config is not set for the project
- [ ] `POST /api/projects/{project_id}/github/import` returns 404 when project_id does not exist
- [ ] Imported issues appear in `GET /api/projects/{project_id}/issues` with `github_issue_id` set to the GitHub issue number
- [ ] Running import twice does not duplicate issues -- the second run updates existing issues (same `github_issue_id`) rather than creating new ones
- [ ] GitHub issue state `"open"` maps to internal status `"open"` and `"closed"` maps to `"closed"`
- [ ] GitHub issue labels are included in the imported issue description
- [ ] Pull requests returned by the GitHub issues endpoint are filtered out (not imported)
- [ ] The GitHub client raises `GitHubAPIError` on non-200 responses (e.g., invalid token returns a clear error, not a crash)
- [ ] The `since` parameter on the import endpoint filters to issues updated after that timestamp
- [ ] GitHub router is registered in `create_app()` and all endpoints are accessible
- [ ] A new Alembic migration adds the `github_config` JSONB column to the `projects` table
- [ ] `uv run pytest backend/tests/test_github_import.py -v` passes with 20+ tests covering all the above

## Test Scenarios

### Unit: GitHub client (`integrations/github/client.py`)
- `list_issues` returns parsed issue dicts when given a mocked 200 response
- `list_issues` filters out items with `pull_request` key
- `list_issues` handles pagination (mocked Link header with multiple pages)
- `list_issues` with `since` parameter passes it as query param to GitHub API
- `list_issues` raises `GitHubAPIError` on 401 (bad token)
- `list_issues` raises `GitHubAPIError` on 404 (bad repo)
- `get_issue` returns a single issue dict on success

### Unit: Mapper (`integrations/github/mapper.py`)
- `map_github_issue` with state `"open"` returns status `"open"`
- `map_github_issue` with state `"closed"` returns status `"closed"`
- `map_github_issue` truncates title longer than 500 chars
- `map_github_issue` with labels appends label names to description
- `map_github_issue` with no labels leaves description as-is
- `map_github_issue` with null body sets description to None (or label-only string if labels exist)
- `map_github_issue` sets `github_issue_id` to the issue `number`

### Unit: Importer (`integrations/github/importer.py`)
- `import_issues` creates new internal issues for GitHub issues not yet imported (mock client + real DB)
- `import_issues` updates existing internal issues when `github_issue_id` matches (idempotent re-import)
- `import_issues` returns correct `ImportResult` counts (created, updated)
- `import_issues` records errors in `ImportResult.errors` when individual issue creation fails
- `import_issues` passes `since` to the client's `list_issues`

### Integration: API endpoints via AsyncClient
- POST configure returns 200 with masked token
- POST configure with non-existent project returns 404
- POST configure with missing required fields returns 422
- GET status returns `{"configured": false}` before configuration
- GET status returns config with masked token after configuration
- GET status with non-existent project returns 404
- POST import with mocked GitHub client returns 200 with created/updated counts
- POST import without prior configure returns 400
- POST import with non-existent project returns 404
- POST import twice with same GitHub issues: first creates, second updates (no duplicates)
- POST import with `since` parameter passes it through to the client
- Imported issues are visible via `GET /api/projects/{project_id}/issues` with `github_issue_id` populated
- GitHub router is registered and endpoints respond (not 404 from missing route)

## Log

### [SWE] 2026-03-15 14:30
- Implemented full GitHub issue import feature: client, mapper, importer, API routes
- GitHub client uses httpx.AsyncClient with pagination, PR filtering, and GitHubAPIError
- Mapper converts GitHub issue fields to internal format with label appending and title truncation
- Importer performs upsert (create or update) based on github_issue_id match per project
- API endpoints: POST configure (stores config in dedicated github_config JSONB column), GET status (masked token), POST import (triggers import with optional since param)
- Added github_config JSONB column to Project model and created Alembic migration
- Added github_default_token to Settings config
- Registered github_router in create_app()
- Files created:
  - backend/codehive/integrations/__init__.py
  - backend/codehive/integrations/github/__init__.py
  - backend/codehive/integrations/github/client.py
  - backend/codehive/integrations/github/mapper.py
  - backend/codehive/integrations/github/importer.py
  - backend/codehive/api/schemas/github.py
  - backend/codehive/api/routes/github.py
  - backend/codehive/db/migrations/versions/a1b2c3d4e5f6_add_github_config_to_projects.py
  - backend/tests/test_github_import.py
- Files modified:
  - backend/codehive/api/app.py (registered github_router)
  - backend/codehive/config.py (added github_default_token)
  - backend/codehive/db/models.py (added github_config column to Project)
- Tests added: 33 tests covering client (7), mapper (8), importer (5), API endpoints (13)
- Build results: 718 tests pass (full suite), 0 fail, ruff clean
- No known limitations

### [QA] 2026-03-15 15:10
- Tests: 33 passed (test_github_import.py), 718 passed (full suite), 0 failed
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. POST configure returns 200 with masked token: PASS
  2. POST configure with non-existent project returns 404: PASS
  3. GET status returns configured=true with all fields after configure: PASS
  4. GET status returns configured=false when no config set: PASS
  5. POST import returns 200 with created/updated/errors: PASS
  6. POST import returns 400 when config not set: PASS
  7. POST import returns 404 when project does not exist: PASS
  8. Imported issues appear in GET issues with github_issue_id: PASS
  9. Running import twice does not duplicate issues: PASS
  10. GitHub state open->open, closed->closed: PASS
  11. Labels included in imported description: PASS
  12. Pull requests filtered out: PASS
  13. GitHubAPIError raised on non-200 responses: PASS
  14. since parameter filters issues: PASS
  15. GitHub router registered in create_app(): PASS
  16. Alembic migration adds github_config JSONB column: PASS
  17. 20+ tests covering all criteria (33 tests): PASS
- Note: unrelated deletion of docs/tracker/14-react-app-scaffolding.todo.md in working tree (not part of this issue)
- VERDICT: PASS

### [PM] 2026-03-15 15:45
- Reviewed diff: 10 files changed (3 modified, 7 new), plus Alembic migration
- Code review summary:
  - `client.py`: Clean httpx-based GitHub API client with pagination, PR filtering, and GitHubAPIError. Correct Link header parsing.
  - `mapper.py`: Straightforward field mapping with title truncation and label appending. Handles null body correctly.
  - `importer.py`: Proper upsert logic via github_issue_id lookup. Uses dependency injection for testability. Returns ImportResult dataclass with error recording.
  - `api/routes/github.py`: Three endpoints (configure, status, import) with correct error codes (404, 400, 422). Token masking applied. last_import_at updated on successful import.
  - `api/schemas/github.py`: Clean Pydantic models with field validation (min_length=1).
  - Alembic migration: Correct JSONB column addition with nullable=True.
  - Tests: 33 tests covering client (7), mapper (8), importer (5), API endpoints (13). Tests use proper mocking, real DB fixtures, and validate both happy paths and error cases.
- Results verified: 33/33 tests pass (confirmed by running `uv run pytest backend/tests/test_github_import.py -v`)
- Acceptance criteria: all 17/17 met
  1. POST configure returns 200 with masked token: MET
  2. POST configure with non-existent project returns 404: MET
  3. GET status returns configured=true with all fields: MET
  4. GET status returns configured=false when no config: MET
  5. POST import returns 200 with created/updated/errors: MET
  6. POST import returns 400 when config not set: MET
  7. POST import returns 404 when project doesn't exist: MET
  8. Imported issues visible via issues API with github_issue_id: MET
  9. Import twice no duplicates (upsert): MET
  10. State mapping open->open, closed->closed: MET
  11. Labels included in description: MET
  12. PRs filtered out: MET
  13. GitHubAPIError on non-200 responses: MET
  14. since parameter filters issues: MET
  15. GitHub router registered in create_app(): MET
  16. Alembic migration adds github_config JSONB column: MET
  17. 20+ tests (33 tests): MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
