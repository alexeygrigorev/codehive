# Issue #94a: Project-by-path API and auto-create

Parent: #94

## Problem

There is no way to look up a project by its filesystem path. The `codehive code /path/to/folder` command needs to resolve a directory to a project in the database. Currently the only project lookup is by UUID (`GET /api/projects/{id}`), which is useless when all you have is a directory path.

## Dependencies

- #88b (remove workspaces) must be `.done.md` -- projects must be top-level (no workspace_id required for creation)

## Scope

### Backend -- Core logic

1. **Add `get_project_by_path()` to `core/project.py`:**
   - Takes a normalized absolute path string
   - Queries `Project` table where `path == normalized_path`
   - Returns `Project | None`

2. **Add `get_or_create_project_by_path()` to `core/project.py`:**
   - Takes an absolute path string
   - Calls `get_project_by_path()` first
   - If found, returns the existing project
   - If not found, creates a new project with `name = os.path.basename(path)` and `path = normalized_path`
   - Returns `(project, created: bool)` tuple

### Backend -- API route

3. **Add `GET /api/projects/by-path` endpoint to `api/routes/projects.py`:**
   - Query parameter: `path` (required, string)
   - Normalizes the path (resolve symlinks, ensure absolute)
   - Returns the project if found, or 404
   - Response uses existing `ProjectRead` schema

4. **Add `POST /api/projects/by-path` endpoint to `api/routes/projects.py`:**
   - Body: `{"path": "/absolute/path"}` (required)
   - Calls `get_or_create_project_by_path()`
   - Returns 200 with the project if it already existed
   - Returns 201 with the project if it was newly created
   - Response uses existing `ProjectRead` schema

### Backend -- Tests

5. **Unit tests in `tests/test_project_by_path.py`:**
   - `get_project_by_path()` returns None for unknown path
   - `get_project_by_path()` returns project for known path
   - `get_or_create_project_by_path()` creates project with correct name from path basename
   - `get_or_create_project_by_path()` returns existing project on second call (idempotent)
   - Path normalization: trailing slashes stripped, path is absolute

6. **Integration tests:**
   - `GET /api/projects/by-path?path=/nonexistent` returns 404
   - `POST /api/projects/by-path` with new path returns 201 + project with correct name
   - `POST /api/projects/by-path` with existing path returns 200 + same project (idempotent)
   - `GET /api/projects/by-path?path=...` returns the created project

## Acceptance Criteria

- [ ] `get_project_by_path("/some/path")` returns `None` when no project has that path
- [ ] `get_project_by_path("/some/path")` returns the correct `Project` when one exists with that path
- [ ] `get_or_create_project_by_path("/home/user/git/myapp")` creates a project named `"myapp"` with path `"/home/user/git/myapp"`
- [ ] `get_or_create_project_by_path()` is idempotent -- calling twice with the same path returns the same project
- [ ] `GET /api/projects/by-path?path=/nonexistent` returns 404
- [ ] `POST /api/projects/by-path {"path": "/home/user/git/myapp"}` returns 201 on first call with a valid project
- [ ] `POST /api/projects/by-path {"path": "/home/user/git/myapp"}` returns 200 on second call with the same project ID
- [ ] Trailing slashes in paths are normalized (e.g., `/foo/bar/` treated same as `/foo/bar`)
- [ ] `uv run pytest tests/ -v` passes with 6+ new tests
- [ ] `uv run ruff check` passes

## Test Scenarios

### Unit: get_project_by_path
- Query with unknown path returns None
- Query with known path returns correct project
- Path with trailing slash matches path without trailing slash

### Unit: get_or_create_project_by_path
- First call creates project, returns `(project, created=True)`
- Second call with same path returns `(project, created=False)` with same ID
- Name is derived from path basename (`/home/user/git/myapp` -> `"myapp"`)

### Integration: API endpoints
- `GET /api/projects/by-path?path=/nonexistent` -> 404
- `POST /api/projects/by-path {"path": "/tmp/testproject"}` -> 201 with project data
- `POST /api/projects/by-path {"path": "/tmp/testproject"}` -> 200 with same project ID
- `GET /api/projects/by-path?path=/tmp/testproject` -> 200 with project data

## Notes

- The `Project.path` column already exists as `Unicode(1024), nullable=True` -- no migration needed
- No workspace_id needed after #88b
- Path normalization should strip trailing slashes and resolve to absolute path on the server side
- This is pure backend work -- no CLI or frontend changes

## Log

### [SWE] 2026-03-17 12:00
- Added `normalize_path()`, `get_project_by_path()`, `get_or_create_project_by_path()` to `core/project.py`
- Added `GET /api/projects/by-path` and `POST /api/projects/by-path` endpoints to `api/routes/projects.py`
- `get_or_create_project_by_path()` accepts optional `workspace_id` (needed until #88b removes workspaces)
- By-path endpoints do not require auth (no user context needed for path-based lookup/create)
- Path normalization uses `os.path.normpath(os.path.abspath(path))` to strip trailing slashes and resolve paths
- Files modified: `backend/codehive/core/project.py`, `backend/codehive/api/routes/projects.py`
- Files created: `backend/tests/test_project_by_path.py`
- Tests added: 13 tests (3 normalize_path, 3 get_project_by_path, 3 get_or_create_project_by_path, 4 API integration)
- Build results: 13/13 new tests pass, ruff clean on modified files. Full suite: 1706 passed, 26 pre-existing errors in other files
- Known limitations: `workspace_id` is still required in the DB schema (nullable=False); `get_or_create_project_by_path` accepts optional `workspace_id` param for project creation. Once #88b lands this can be simplified.
