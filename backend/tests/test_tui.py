"""Tests for the Textual TUI client."""

from __future__ import annotations

import uuid
from io import StringIO
from unittest.mock import MagicMock

import httpx
import pytest

from codehive.clients.terminal.api_client import APIClient
from codehive.clients.terminal.app import CodehiveApp
from codehive.clients.terminal.widgets.status_indicator import StatusIndicator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_A_ID = str(uuid.uuid4())
_PROJECT_B_ID = str(uuid.uuid4())
_SESSION_1_ID = str(uuid.uuid4())
_SESSION_2_ID = str(uuid.uuid4())

MOCK_PROJECTS = [
    {
        "id": _PROJECT_A_ID,
        "name": "Alpha",
        "path": "/home/alpha",
        "description": "Alpha project description that is quite long and should be truncated",
        "created_at": "2026-01-01T00:00:00",
    },
    {
        "id": _PROJECT_B_ID,
        "name": "Beta",
        "path": "/home/beta",
        "description": "Beta desc",
        "created_at": "2026-01-02T00:00:00",
    },
]

MOCK_SESSIONS_A = [
    {
        "id": _SESSION_1_ID,
        "name": "sess-1",
        "engine": "native",
        "mode": "execution",
        "status": "executing",
        "created_at": "2026-01-01T00:00:00",
    },
    {
        "id": _SESSION_2_ID,
        "name": "sess-2",
        "engine": "claude_code",
        "mode": "brainstorm",
        "status": "failed",
        "created_at": "2026-01-02T00:00:00",
    },
]

MOCK_SESSIONS_B: list[dict] = []


def _build_mock_api() -> MagicMock:
    """Return a mocked APIClient that returns known data."""
    api = MagicMock(spec=APIClient)
    api.list_projects.return_value = MOCK_PROJECTS
    api.get_project.side_effect = lambda pid: next(
        (p for p in MOCK_PROJECTS if p["id"] == pid), {"name": "Unknown", "description": ""}
    )

    def _list_sessions(pid: str) -> list[dict]:
        if pid == _PROJECT_A_ID:
            return MOCK_SESSIONS_A
        return MOCK_SESSIONS_B

    api.list_sessions.side_effect = _list_sessions
    api.list_questions.return_value = []
    return api


def _build_empty_mock_api() -> MagicMock:
    """Return a mocked APIClient with empty data."""
    api = MagicMock(spec=APIClient)
    api.list_projects.return_value = []
    api.list_sessions.return_value = []
    api.list_questions.return_value = []
    return api


def _build_error_mock_api() -> MagicMock:
    """Return a mocked APIClient that raises connection errors."""
    api = MagicMock(spec=APIClient)
    api.list_projects.side_effect = httpx.ConnectError("Connection refused")
    api.list_sessions.side_effect = httpx.ConnectError("Connection refused")
    api.list_questions.side_effect = httpx.ConnectError("Connection refused")
    return api


# ---------------------------------------------------------------------------
# Unit: API client wrapper
# ---------------------------------------------------------------------------


class TestAPIClient:
    def test_builds_correct_urls(self) -> None:
        client = APIClient("http://localhost:7433")
        assert client.build_url("/api/projects") == "http://localhost:7433/api/projects"

    def test_strips_trailing_slash(self) -> None:
        client = APIClient("http://localhost:7433/")
        assert client.base_url == "http://localhost:7433"
        assert client.build_url("/api/projects") == "http://localhost:7433/api/projects"

    def test_get_returns_parsed_json(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": "1", "name": "test"}]
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:7433")
        client._client = MagicMock()
        client._client.get.return_value = mock_response

        result = client.get("/api/projects")
        assert result == [{"id": "1", "name": "test"}]
        client._client.get.assert_called_once_with("/api/projects", params=None)

    def test_get_raises_on_connection_error(self) -> None:
        client = APIClient("http://localhost:7433")
        client._client = MagicMock()
        client._client.get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            client.get("/api/projects")


# ---------------------------------------------------------------------------
# Unit: Status indicator widget
# ---------------------------------------------------------------------------


class TestStatusIndicator:
    @pytest.mark.parametrize(
        "status,expected_class",
        [
            ("idle", "status-idle"),
            ("executing", "status-executing"),
            ("completed", "status-completed"),
            ("failed", "status-failed"),
            ("waiting_input", "status-waiting"),
        ],
    )
    def test_renders_correct_class(self, status: str, expected_class: str) -> None:
        widget = StatusIndicator(status)
        assert expected_class in widget.classes

    def test_unknown_status_uses_default(self) -> None:
        widget = StatusIndicator("nonexistent_status")
        assert "status-unknown" in widget.classes
        assert widget.class_suffix == "unknown"


# ---------------------------------------------------------------------------
# Unit: Dashboard screen
# ---------------------------------------------------------------------------


class TestDashboardScreen:
    @pytest.mark.asyncio
    async def test_dashboard_composes_and_mounts(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)):
            # Dashboard should be the active screen
            from codehive.clients.terminal.screens.dashboard import DashboardScreen

            assert isinstance(app.screen, DashboardScreen)

    @pytest.mark.asyncio
    async def test_dashboard_shows_summary_counts(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from codehive.clients.terminal.screens.dashboard import SummaryCard

            projects_card = app.screen.query_one("#card-projects", SummaryCard)
            assert projects_card._value == 2

            active_card = app.screen.query_one("#card-active", SummaryCard)
            # sess-1 is executing (active), sess-2 is failed (not active)
            assert active_card._value == 1

            failed_card = app.screen.query_one("#card-failed", SummaryCard)
            assert failed_card._value == 1

    @pytest.mark.asyncio
    async def test_dashboard_shows_no_projects_message(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_empty_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from textual.widgets import Static

            no_proj = app.screen.query_one("#no-projects", Static)
            assert no_proj.display is True
            # Access the internal content via name-mangled attribute
            content = str(getattr(no_proj, "_Static__content", ""))
            assert "No projects" in content


# ---------------------------------------------------------------------------
# Unit: Project list screen
# ---------------------------------------------------------------------------


class TestProjectListScreen:
    @pytest.mark.asyncio
    async def test_project_list_renders_rows(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.project_list import ProjectListScreen

            app.push_screen(ProjectListScreen())
            await pilot.pause()

            from codehive.clients.terminal.widgets.data_table import StyledDataTable

            table = app.screen.query_one("#pl-table", StyledDataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_project_list_select_pushes_detail(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.project_list import ProjectListScreen

            app.push_screen(ProjectListScreen())
            await pilot.pause()

            from codehive.clients.terminal.widgets.data_table import StyledDataTable

            table = app.screen.query_one("#pl-table", StyledDataTable)
            table.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.pause()

            from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

            assert isinstance(app.screen, ProjectDetailScreen)


# ---------------------------------------------------------------------------
# Unit: Project detail screen
# ---------------------------------------------------------------------------


class TestProjectDetailScreen:
    @pytest.mark.asyncio
    async def test_project_detail_shows_name_and_description(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

            app.push_screen(ProjectDetailScreen(_PROJECT_A_ID))
            await pilot.pause()

            from textual.widgets import Static

            name_widget = app.screen.query_one("#pd-name", Static)
            content = str(getattr(name_widget, "_Static__content", ""))
            assert "Alpha" in content

    @pytest.mark.asyncio
    async def test_project_detail_lists_sessions(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

            app.push_screen(ProjectDetailScreen(_PROJECT_A_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.data_table import StyledDataTable

            table = app.screen.query_one("#pd-table", StyledDataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_project_detail_escape_pops_back(self) -> None:
        app = CodehiveApp(base_url="http://test:7433")
        app.api_client = _build_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.dashboard import DashboardScreen
            from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

            app.push_screen(ProjectDetailScreen(_PROJECT_A_ID))
            await pilot.pause()
            assert isinstance(app.screen, ProjectDetailScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)


# ---------------------------------------------------------------------------
# Integration: CLI entry point
# ---------------------------------------------------------------------------


class TestCLIEntryPoint:
    def test_tui_subcommand_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The 'tui' subcommand is recognized by argparse."""
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive", "tui", "--help"])
        out = StringIO()
        monkeypatch.setattr("sys.stdout", out)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert "tui" in out.getvalue() or "dashboard" in out.getvalue().lower()

    def test_tui_help_prints_usage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """codehive tui --help should mention the dashboard / TUI."""
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive", "--help"])
        out = StringIO()
        monkeypatch.setattr("sys.stdout", out)
        with pytest.raises(SystemExit):
            main()
        output = out.getvalue()
        assert "tui" in output
