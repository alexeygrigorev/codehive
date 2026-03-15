# 27: Terminal Client - Dashboard and Navigation

## Description
Build the Textual TUI application shell with a dashboard showing active projects, sessions, pending questions, and failed agents. Implement keyboard-driven navigation between views. The TUI is an HTTP client that talks to the backend REST API (same pattern as the CLI in `cli.py`), using `httpx` for data fetching.

## Scope
- `backend/codehive/clients/terminal/__init__.py` -- Package init
- `backend/codehive/clients/terminal/app.py` -- Textual App subclass, main entry point
- `backend/codehive/clients/terminal/api_client.py` -- Shared httpx wrapper for all TUI screens (base URL from env/config, reuses `CODEHIVE_BASE_URL`)
- `backend/codehive/clients/terminal/screens/__init__.py` -- Package init
- `backend/codehive/clients/terminal/screens/dashboard.py` -- Dashboard screen: summary counts, active projects list, recent sessions, pending questions count, failed sessions count
- `backend/codehive/clients/terminal/screens/project_list.py` -- Full project list with selection to navigate to project detail
- `backend/codehive/clients/terminal/screens/project_detail.py` -- Single project view: name, description, sessions list with status
- `backend/codehive/clients/terminal/widgets/__init__.py` -- Package init
- `backend/codehive/clients/terminal/widgets/status_indicator.py` -- Reusable status badge widget (idle/executing/failed/etc.)
- `backend/codehive/clients/terminal/widgets/data_table.py` -- Reusable styled data table widget
- `backend/codehive/cli.py` -- Add `codehive tui` subcommand to launch the Textual app
- `backend/tests/test_tui.py` -- TUI widget and screen tests
- `backend/pyproject.toml` -- Add `textual` dependency

## Dependencies
- Depends on: #04 (project CRUD API) -- DONE
- Depends on: #05 (session CRUD API) -- DONE
- Depends on: #10 (session scheduler, provides session status data) -- DONE

## Out of Scope (handled by #28)
- Session detail/chat view
- WebSocket live streaming in TUI
- ToDo, timeline, changed-files panels

## Acceptance Criteria

- [ ] `textual` is added to `backend/pyproject.toml` dependencies and `uv sync` succeeds
- [ ] `codehive tui` launches a Textual application that renders the dashboard screen
- [ ] Dashboard screen fetches data from the backend API via httpx (GET /api/projects, GET /api/projects/{id}/sessions, GET /api/sessions/{id}/questions?answered=false)
- [ ] Dashboard displays: project count, active session count (status != completed/failed), pending question count, and failed session count
- [ ] Dashboard shows a list of projects with name and session count per project
- [ ] Project list screen shows all projects in a table with columns: Name, Path, Description (truncated), Created
- [ ] Selecting a project in the project list navigates to the project detail screen
- [ ] Project detail screen shows the project name, description, and a table of its sessions with columns: Name, Engine, Mode, Status
- [ ] Keyboard navigation works: Tab/Shift-Tab between widgets, Enter to select, Escape/Backspace to go back, q to quit
- [ ] A key binding bar (footer) shows available keys on every screen
- [ ] Status indicator widget renders distinct visual styles for at least: idle, executing, waiting_input, completed, failed
- [ ] The `codehive tui` command accepts `--base-url` flag (falls back to CODEHIVE_BASE_URL env var, then http://127.0.0.1:8000)
- [ ] `uv run pytest tests/test_tui.py -v` passes with 8+ tests

## Test Scenarios

### Unit: API client wrapper
- api_client builds correct URLs from base_url
- api_client returns parsed JSON for successful GET requests
- api_client raises or returns error info for connection failure (server not running)

### Unit: Status indicator widget
- StatusIndicator renders with correct style class for each session status value (idle, executing, completed, failed, waiting_input)
- StatusIndicator with unknown status falls back to a default style

### Unit: Dashboard screen
- Dashboard screen can be composed and mounted (using Textual's App.run_test)
- Dashboard correctly populates summary counts from mocked API responses (mock httpx to return known project/session data)
- Dashboard shows "No projects" message when API returns empty list

### Unit: Project list screen
- Project list screen renders a table row for each project from mocked API data
- Selecting a row pushes the project detail screen (verify screen stack)

### Unit: Project detail screen
- Project detail screen shows project name and description from mocked data
- Project detail screen lists sessions in a table from mocked API data
- Pressing Escape pops back to the previous screen

### Integration: CLI entry point
- `codehive tui --help` prints usage without error
- The `tui` subcommand is registered in the argparse CLI

## Technical Notes
- Use `textual.app.App` as the base class with `push_screen()` / `pop_screen()` navigation
- The API client should be a thin synchronous httpx wrapper (Textual has its own async model; use `run_worker` for HTTP calls to avoid blocking the UI thread)
- Mock the httpx calls in tests -- do NOT require a running backend server for test_tui.py
- Follow the same base URL resolution pattern as `cli.py` (_get_base_url)
- Session statuses are defined in the product spec: idle, planning, executing, waiting_input, waiting_approval, blocked, completed, failed

## Log

### [SWE] 2026-03-15 12:00
- Added `textual>=8.1.1` to `backend/pyproject.toml` dependencies
- Created full TUI package structure under `backend/codehive/clients/terminal/`
- Implemented `APIClient` (thin synchronous httpx wrapper with convenience methods for projects, sessions, questions)
- Implemented `StatusIndicator` widget with distinct CSS classes for all 8 session statuses plus unknown fallback
- Implemented `StyledDataTable` widget (thin DataTable wrapper)
- Implemented `DashboardScreen` with 4 summary cards (projects, active sessions, pending questions, failed sessions), project list table, and "No projects" message
- Implemented `ProjectListScreen` with columns: Name, Path, Description (truncated to 40 chars), Created
- Implemented `ProjectDetailScreen` with project name/description and sessions table (Name, Engine, Mode, Status)
- Implemented `CodehiveApp` (Textual App subclass) that pushes DashboardScreen on mount
- Added `codehive tui` subcommand to CLI (uses existing `_get_base_url` for `--base-url` / env var / default resolution)
- All screens use `@work(thread=True)` for HTTP calls to avoid blocking UI thread
- Keyboard navigation: Tab/Shift-Tab (built-in), Enter to select rows, Escape/Backspace to go back, q to quit, p for project list from dashboard
- Footer with key bindings on every screen
- Tests mock the APIClient directly (no running server needed)
- Files created: `backend/codehive/clients/__init__.py`, `backend/codehive/clients/terminal/__init__.py`, `backend/codehive/clients/terminal/api_client.py`, `backend/codehive/clients/terminal/app.py`, `backend/codehive/clients/terminal/screens/__init__.py`, `backend/codehive/clients/terminal/screens/dashboard.py`, `backend/codehive/clients/terminal/screens/project_list.py`, `backend/codehive/clients/terminal/screens/project_detail.py`, `backend/codehive/clients/terminal/widgets/__init__.py`, `backend/codehive/clients/terminal/widgets/status_indicator.py`, `backend/codehive/clients/terminal/widgets/data_table.py`, `backend/tests/test_tui.py`
- Files modified: `backend/codehive/cli.py`, `backend/pyproject.toml`
- Tests added: 20 tests (4 API client, 6 status indicator, 3 dashboard, 2 project list, 3 project detail, 2 CLI entry point)
- Build results: 20 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 14:30
- Tests: 435 passed (full suite), 0 failed; 20 TUI-specific tests all pass
- Ruff check: clean (codehive/clients/terminal/, tests/test_tui.py, codehive/cli.py)
- Ruff format: clean (12 files already formatted)
- Acceptance criteria:
  1. `textual` added to pyproject.toml dependencies, `uv sync` succeeded: PASS
  2. `codehive tui` launches Textual app rendering dashboard screen: PASS (CodehiveApp.on_mount pushes DashboardScreen; test confirms)
  3. Dashboard fetches data via httpx (GET /api/projects, sessions, questions): PASS (APIClient has list_projects, list_sessions, list_questions; DashboardScreen._load_data calls them)
  4. Dashboard displays project count, active session count, pending question count, failed session count: PASS (4 SummaryCard widgets; test verifies values)
  5. Dashboard shows project list with name and session count: PASS (StyledDataTable with Name/Sessions columns populated from API data)
  6. Project list screen shows table with Name, Path, Description (truncated), Created: PASS (columns added in on_mount; description truncated to 40 chars)
  7. Selecting project in list navigates to project detail: PASS (on_data_table_row_selected pushes ProjectDetailScreen; test verifies screen change)
  8. Project detail shows name, description, sessions table with Name, Engine, Mode, Status: PASS (Static widgets for name/desc; DataTable with 4 columns)
  9. Keyboard navigation (Tab/Shift-Tab, Enter, Escape/Backspace, q): PASS (BINDINGS defined on all screens; test_project_detail_escape_pops_back verifies Escape)
  10. Key binding bar (Footer) on every screen: PASS (Footer() yielded in compose() of DashboardScreen, ProjectListScreen, ProjectDetailScreen)
  11. StatusIndicator renders distinct styles for idle, executing, waiting_input, completed, failed: PASS (8 statuses + unknown fallback; parametrized tests cover 5 statuses + unknown)
  12. `codehive tui` accepts `--base-url` flag, falls back to env var, then default: PASS (--base-url on top-level parser; _get_base_url checks args, CODEHIVE_BASE_URL env, then http://127.0.0.1:8000)
  13. `uv run pytest tests/test_tui.py -v` passes with 8+ tests: PASS (20 tests pass)
- Code quality: type hints used throughout, proper error handling (try/except in worker threads), no hardcoded values, follows existing CLI patterns, uses @work(thread=True) for non-blocking HTTP
- VERDICT: PASS

### [PM] 2026-03-15 15:00
- Reviewed diff: 14 files changed (12 new, 2 modified: cli.py, pyproject.toml)
- Results verified: real data present -- 20 TUI tests pass in 1.65s, all screens render with mocked API data, keyboard navigation tested, CLI entry point confirmed
- Acceptance criteria: all 13 met
  1. textual added to pyproject.toml, uv sync succeeds: MET
  2. codehive tui launches Textual app with dashboard: MET
  3. Dashboard fetches via httpx (projects, sessions, questions): MET
  4. Dashboard displays 4 summary counts: MET (test verifies values)
  5. Dashboard shows project list with name + session count: MET
  6. Project list with Name, Path, Description (truncated to 40), Created: MET
  7. Project selection navigates to detail: MET (test verifies screen push)
  8. Project detail shows name, description, sessions table (Name, Engine, Mode, Status): MET
  9. Keyboard nav (Tab, Enter, Escape/Backspace, q): MET (bindings on all screens, test verifies Escape pop)
  10. Footer key binding bar on every screen: MET (Footer() in all 3 screen compose methods)
  11. StatusIndicator distinct styles for 5+ statuses: MET (8 statuses + unknown fallback, parametrized tests)
  12. --base-url flag with env var and default fallback: MET (top-level parser, _get_base_url cascade)
  13. 8+ tests pass: MET (20 tests pass)
- Code quality: clean, follows existing patterns, proper use of @work(thread=True), mocked API tests, type hints throughout
- Follow-up issues created: none needed
- VERDICT: ACCEPT
