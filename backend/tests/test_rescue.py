"""Tests for the TUI rescue mode (issue #30)."""

from __future__ import annotations

import uuid
from io import StringIO
from unittest.mock import MagicMock

import httpx
import pytest

from codehive.clients.terminal.api_client import APIClient
from codehive.clients.terminal.screens.rescue import (
    HealthBanner,
    RescueApp,
    RescueScreen,
)
from codehive.clients.terminal.widgets.data_table import StyledDataTable

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_PROJECT_ID = str(uuid.uuid4())
_SESSION_FAILED_ID = str(uuid.uuid4())
_SESSION_WAITING_ID = str(uuid.uuid4())
_SESSION_OK_ID = str(uuid.uuid4())
_QUESTION_ID = str(uuid.uuid4())
_CHECKPOINT_ID = str(uuid.uuid4())

MOCK_HEALTH = {
    "version": "0.1.0",
    "database": "up",
    "redis": "up",
    "active_sessions": 3,
    "maintenance": False,
}

MOCK_HEALTH_DEGRADED = {
    "version": "0.1.0",
    "database": "down",
    "redis": "up",
    "active_sessions": 0,
    "maintenance": True,
}

MOCK_PROJECTS = [
    {
        "id": _PROJECT_ID,
        "name": "TestProject",
        "path": "/test",
        "created_at": "2026-01-01T00:00:00",
    },
]

MOCK_SESSIONS = [
    {
        "id": _SESSION_FAILED_ID,
        "name": "broken-agent",
        "engine": "native",
        "mode": "execution",
        "status": "failed",
        "project_id": _PROJECT_ID,
        "created_at": "2026-01-01T00:00:00",
    },
    {
        "id": _SESSION_WAITING_ID,
        "name": "waiting-agent",
        "engine": "native",
        "mode": "execution",
        "status": "waiting_input",
        "project_id": _PROJECT_ID,
        "created_at": "2026-01-01T01:00:00",
    },
    {
        "id": _SESSION_OK_ID,
        "name": "ok-agent",
        "engine": "native",
        "mode": "execution",
        "status": "executing",
        "project_id": _PROJECT_ID,
        "created_at": "2026-01-01T02:00:00",
    },
]

MOCK_QUESTIONS = [
    {
        "id": _QUESTION_ID,
        "session_id": _SESSION_WAITING_ID,
        "question": "Which database adapter should I use?",
        "answered": False,
        "created_at": "2026-01-01T01:30:00",
    },
]

MOCK_CHECKPOINTS = [
    {
        "id": _CHECKPOINT_ID,
        "session_id": _SESSION_FAILED_ID,
        "label": "before-migration",
        "created_at": "2026-01-01T00:30:00",
    },
]


def _build_rescue_api() -> MagicMock:
    """Mock APIClient with rescue-relevant data."""
    api = MagicMock(spec=APIClient)
    api.get_system_health.return_value = MOCK_HEALTH
    api.list_projects.return_value = MOCK_PROJECTS
    api.list_sessions.return_value = MOCK_SESSIONS

    def _list_questions(session_id: str, answered: bool | None = None) -> list[dict]:
        if session_id == _SESSION_WAITING_ID and answered is False:
            return MOCK_QUESTIONS
        return []

    api.list_questions.side_effect = _list_questions
    api.list_checkpoints.return_value = MOCK_CHECKPOINTS
    api.pause_session.return_value = {"status": "paused"}
    api.resume_session.return_value = {"status": "running"}
    api.rollback_checkpoint.return_value = {"status": "rolled_back"}
    api.answer_question.return_value = {"status": "answered"}
    api.set_maintenance.return_value = {"maintenance": True}
    return api


def _build_empty_api() -> MagicMock:
    """Mock APIClient with no data."""
    api = MagicMock(spec=APIClient)
    api.get_system_health.return_value = MOCK_HEALTH
    api.list_projects.return_value = []
    api.list_sessions.return_value = []
    api.list_questions.return_value = []
    api.list_checkpoints.return_value = []
    return api


def _build_error_api() -> MagicMock:
    """Mock APIClient that raises connection errors."""
    api = MagicMock(spec=APIClient)
    api.get_system_health.side_effect = httpx.ConnectError("Connection refused")
    api.list_projects.side_effect = httpx.ConnectError("Connection refused")
    api.list_sessions.side_effect = httpx.ConnectError("Connection refused")
    api.list_questions.side_effect = httpx.ConnectError("Connection refused")
    return api


# ---------------------------------------------------------------------------
# Unit: APIClient rescue methods
# ---------------------------------------------------------------------------


class TestAPIClientRescueMethods:
    def test_pause_session_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "paused"}
        mock_resp.raise_for_status = MagicMock()
        client._client.post.return_value = mock_resp

        result = client.pause_session("sess-123")
        client._client.post.assert_called_once_with("/api/sessions/sess-123/pause", json=None)
        assert result == {"status": "paused"}

    def test_list_checkpoints_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": "cp-1"}]
        mock_resp.raise_for_status = MagicMock()
        client._client.get.return_value = mock_resp

        result = client.list_checkpoints("sess-123")
        client._client.get.assert_called_once_with(
            "/api/sessions/sess-123/checkpoints", params=None
        )
        assert result == [{"id": "cp-1"}]

    def test_rollback_checkpoint_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "rolled_back"}
        mock_resp.raise_for_status = MagicMock()
        client._client.post.return_value = mock_resp

        result = client.rollback_checkpoint("cp-456")
        client._client.post.assert_called_once_with("/api/checkpoints/cp-456/rollback", json=None)
        assert result == {"status": "rolled_back"}

    def test_answer_question_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "answered"}
        mock_resp.raise_for_status = MagicMock()
        client._client.post.return_value = mock_resp

        result = client.answer_question("sess-1", "q-1", "Use PostgreSQL")
        client._client.post.assert_called_once_with(
            "/api/sessions/sess-1/questions/q-1/answer",
            json={"answer": "Use PostgreSQL"},
        )
        assert result == {"status": "answered"}

    def test_get_system_health_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_HEALTH
        mock_resp.raise_for_status = MagicMock()
        client._client.get.return_value = mock_resp

        result = client.get_system_health()
        client._client.get.assert_called_once_with("/api/system/health", params=None)
        assert result["version"] == "0.1.0"

    def test_resume_session_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "running"}
        mock_resp.raise_for_status = MagicMock()
        client._client.post.return_value = mock_resp

        result = client.resume_session("sess-123")
        client._client.post.assert_called_once_with("/api/sessions/sess-123/resume", json=None)
        assert result == {"status": "running"}

    def test_set_maintenance_calls_correct_endpoint(self) -> None:
        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"maintenance": True}
        mock_resp.raise_for_status = MagicMock()
        client._client.post.return_value = mock_resp

        result = client.set_maintenance(True)
        client._client.post.assert_called_once_with(
            "/api/system/maintenance", json={"enabled": True}
        )
        assert result == {"maintenance": True}


# ---------------------------------------------------------------------------
# Unit: RescueScreen composition
# ---------------------------------------------------------------------------


class TestRescueScreenComposition:
    @pytest.mark.asyncio
    async def test_screen_composes_with_all_widgets(self) -> None:
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_rescue_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)):
            assert isinstance(app.screen, RescueScreen)
            # Verify key widgets exist
            app.screen.query_one("#rescue-health", HealthBanner)
            app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            app.screen.query_one("#rescue-questions-table", StyledDataTable)

    @pytest.mark.asyncio
    async def test_screen_renders_at_80x24(self) -> None:
        """Minimum phone-over-SSH size."""
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_rescue_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, RescueScreen)

    @pytest.mark.asyncio
    async def test_screen_renders_at_120x40(self) -> None:
        """Larger terminal size."""
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_rescue_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, RescueScreen)


# ---------------------------------------------------------------------------
# Unit: RescueScreen data loading
# ---------------------------------------------------------------------------


class TestRescueScreenDataLoading:
    @pytest.mark.asyncio
    async def test_populates_sessions_and_questions(self) -> None:
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_rescue_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            sessions_table = app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            # Should have 2 failed/stuck sessions (failed + waiting_input), not the OK one
            assert sessions_table.row_count == 2

            questions_table = app.screen.query_one("#rescue-questions-table", StyledDataTable)
            assert questions_table.row_count == 1

    @pytest.mark.asyncio
    async def test_empty_data_shows_empty_messages(self) -> None:
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_empty_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            from textual.widgets import Static

            no_sessions = app.screen.query_one("#rescue-no-sessions", Static)
            assert no_sessions.display is True

            no_questions = app.screen.query_one("#rescue-no-questions", Static)
            assert no_questions.display is True

    @pytest.mark.asyncio
    async def test_connection_error_shows_graceful_state(self) -> None:
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_error_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # Should not crash -- empty tables shown
            sessions_table = app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            assert sessions_table.row_count == 0

    @pytest.mark.asyncio
    async def test_health_banner_reflects_data(self) -> None:
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_rescue_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            banner = app.screen.query_one("#rescue-health", HealthBanner)
            assert "healthy" in banner.classes

    @pytest.mark.asyncio
    async def test_health_banner_degraded(self) -> None:
        api = _build_rescue_api()
        api.get_system_health.return_value = MOCK_HEALTH_DEGRADED
        app = RescueApp(base_url="http://test:8000")
        app.api_client = api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            banner = app.screen.query_one("#rescue-health", HealthBanner)
            assert "degraded" in banner.classes


# ---------------------------------------------------------------------------
# Unit: RescueScreen actions
# ---------------------------------------------------------------------------


class TestRescueScreenActions:
    @pytest.mark.asyncio
    async def test_press_s_calls_pause_session(self) -> None:
        mock_api = _build_rescue_api()
        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Focus the sessions table and select first row
            sessions_table = app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            sessions_table.focus()
            sessions_table.move_cursor(row=0)
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            mock_api.pause_session.assert_called_once_with(_SESSION_FAILED_ID)

    @pytest.mark.asyncio
    async def test_press_a_opens_answer_input(self) -> None:
        mock_api = _build_rescue_api()
        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Focus the questions table
            questions_table = app.screen.query_one("#rescue-questions-table", StyledDataTable)
            questions_table.focus()
            questions_table.move_cursor(row=0)
            await pilot.pause()

            await pilot.press("a")
            await pilot.pause()

            from textual.widgets import Input

            answer_input = app.screen.query_one("#rescue-answer-input", Input)
            assert answer_input.display is True

    @pytest.mark.asyncio
    async def test_press_m_calls_set_maintenance(self) -> None:
        mock_api = _build_rescue_api()
        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            await pilot.press("m")
            await pilot.pause()

            # Health says maintenance=False, so toggle should pass True
            mock_api.set_maintenance.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_press_R_reloads_data(self) -> None:
        mock_api = _build_rescue_api()
        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Reset call counts
            mock_api.get_system_health.reset_mock()
            mock_api.list_projects.reset_mock()

            await pilot.press("R")
            await pilot.pause()

            assert mock_api.get_system_health.called
            assert mock_api.list_projects.called

    @pytest.mark.asyncio
    async def test_press_q_exits_app(self) -> None:
        app = RescueApp(base_url="http://test:8000")
        app.api_client = _build_rescue_api()  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("q")
            # After pressing q, the app should have exited
            # (run_test context handles this gracefully)


# ---------------------------------------------------------------------------
# Unit: RescueScreen restart action
# ---------------------------------------------------------------------------


class TestRescueScreenRestartAction:
    @pytest.mark.asyncio
    async def test_press_x_calls_pause_then_resume(self) -> None:
        mock_api = _build_rescue_api()
        call_order: list[str] = []
        mock_api.pause_session.side_effect = lambda sid: (
            call_order.append("pause"),
            {"status": "paused"},
        )[1]
        mock_api.resume_session.side_effect = lambda sid: (
            call_order.append("resume"),
            {"status": "running"},
        )[1]

        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            sessions_table = app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            sessions_table.focus()
            sessions_table.move_cursor(row=0)
            await pilot.pause()

            await pilot.press("x")
            await pilot.pause()

            mock_api.pause_session.assert_called_once_with(_SESSION_FAILED_ID)
            mock_api.resume_session.assert_called_once_with(_SESSION_FAILED_ID)
            assert call_order == ["pause", "resume"]

    @pytest.mark.asyncio
    async def test_press_x_pause_fails_no_resume(self) -> None:
        mock_api = _build_rescue_api()
        mock_api.pause_session.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock()
        )

        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            sessions_table = app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            sessions_table.focus()
            sessions_table.move_cursor(row=0)
            await pilot.pause()

            await pilot.press("x")
            await pilot.pause()

            mock_api.resume_session.assert_not_called()
            from textual.widgets import Static

            error_widget = app.screen.query_one("#rescue-error", Static)
            assert error_widget.display is True
            assert error_widget.content.startswith("Restart failed:")

    @pytest.mark.asyncio
    async def test_press_x_resume_fails_shows_error(self) -> None:
        mock_api = _build_rescue_api()
        mock_api.resume_session.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock()
        )

        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            sessions_table = app.screen.query_one("#rescue-sessions-table", StyledDataTable)
            sessions_table.focus()
            sessions_table.move_cursor(row=0)
            await pilot.pause()

            await pilot.press("x")
            await pilot.pause()

            mock_api.pause_session.assert_called_once()
            from textual.widgets import Static

            error_widget = app.screen.query_one("#rescue-error", Static)
            assert error_widget.display is True

    @pytest.mark.asyncio
    async def test_press_x_no_sessions_is_noop(self) -> None:
        mock_api = _build_empty_api()
        app = RescueApp(base_url="http://test:8000")
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            await pilot.press("x")
            await pilot.pause()

            mock_api.pause_session.assert_not_called()
            mock_api.resume_session.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: CLI entry point
# ---------------------------------------------------------------------------


class TestRescueCLI:
    def test_rescue_subcommand_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """codehive rescue --help exits 0 and mentions rescue."""
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive", "rescue", "--help"])
        out = StringIO()
        monkeypatch.setattr("sys.stdout", out)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert "rescue" in out.getvalue().lower()

    def test_rescue_creates_rescue_app_not_codehive_app(self) -> None:
        """The rescue subcommand creates a RescueApp, not CodehiveApp."""
        from codehive.clients.terminal.screens.rescue import RescueApp

        app = RescueApp(base_url="http://test:8000")
        assert isinstance(app, RescueApp)
        assert app.TITLE == "Codehive Rescue"
        # Verify it is not a CodehiveApp
        from codehive.clients.terminal.app import CodehiveApp

        assert not isinstance(app, CodehiveApp)

    def test_main_help_includes_rescue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """codehive --help should list rescue subcommand."""
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive", "--help"])
        out = StringIO()
        monkeypatch.setattr("sys.stdout", out)
        with pytest.raises(SystemExit):
            main()
        assert "rescue" in out.getvalue()


# ---------------------------------------------------------------------------
# Unit: HealthBanner
# ---------------------------------------------------------------------------


class TestHealthBanner:
    def test_set_health_healthy(self) -> None:
        banner = HealthBanner()
        banner.set_health(MOCK_HEALTH)
        assert "healthy" in banner.classes
        assert "degraded" not in banner.classes

    def test_set_health_degraded_db_down(self) -> None:
        banner = HealthBanner()
        banner.set_health(
            {
                "version": "1.0",
                "database": "down",
                "redis": "up",
                "active_sessions": 0,
                "maintenance": False,
            }
        )
        assert "degraded" in banner.classes
        assert "healthy" not in banner.classes

    def test_set_health_degraded_maintenance_on(self) -> None:
        banner = HealthBanner()
        banner.set_health(MOCK_HEALTH_DEGRADED)
        assert "degraded" in banner.classes


# ---------------------------------------------------------------------------
# Unit: Dashboard keybinding registration
# ---------------------------------------------------------------------------


class TestDashboardRescueBinding:
    def test_dashboard_bindings_include_rescue(self) -> None:
        """DashboardScreen.BINDINGS contains exclamation_mark -> action_show_rescue."""
        from codehive.clients.terminal.screens.dashboard import DashboardScreen

        found = False
        for binding in DashboardScreen.BINDINGS:
            # Bindings can be tuples (key, action, description) or Binding objects
            if isinstance(binding, tuple):
                key, action, *_ = binding
            else:
                key = binding.key
                action = binding.action
            if key == "exclamation_mark" and action == "show_rescue":
                found = True
                break
        assert found, "DashboardScreen.BINDINGS must include exclamation_mark -> show_rescue"


# ---------------------------------------------------------------------------
# Integration: Dashboard-to-Rescue navigation
# ---------------------------------------------------------------------------


def _build_codehive_app_with_rescue_api():  # type: ignore[no-untyped-def]
    """Build a CodehiveApp with mocked API that supports rescue screen calls."""
    from codehive.clients.terminal.app import CodehiveApp

    api = MagicMock(spec=APIClient)
    api.list_projects.return_value = MOCK_PROJECTS
    api.list_sessions.return_value = MOCK_SESSIONS
    api.list_questions.side_effect = lambda sid, answered=None: (
        MOCK_QUESTIONS if sid == _SESSION_WAITING_ID and answered is False else []
    )
    api.get_system_health.return_value = MOCK_HEALTH
    app = CodehiveApp(base_url="http://test:8000")
    app.api_client = api  # type: ignore[assignment]
    return app


class TestDashboardToRescueNavigation:
    @pytest.mark.asyncio
    async def test_press_exclamation_pushes_rescue_screen(self) -> None:
        """Pressing ! on the dashboard pushes RescueScreen."""
        from codehive.clients.terminal.screens.dashboard import DashboardScreen

        app = _build_codehive_app_with_rescue_api()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            await pilot.press("!")
            await pilot.pause()

            assert isinstance(app.screen, RescueScreen)

    @pytest.mark.asyncio
    async def test_rescue_escape_returns_to_dashboard(self) -> None:
        """Pressing ! then escape returns to the dashboard (round-trip)."""
        from codehive.clients.terminal.screens.dashboard import DashboardScreen

        app = _build_codehive_app_with_rescue_api()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            await pilot.press("!")
            await pilot.pause()
            assert isinstance(app.screen, RescueScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
