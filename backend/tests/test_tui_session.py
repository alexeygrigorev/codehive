"""Tests for the TUI session view (issue #28)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from codehive.clients.terminal.api_client import APIClient
from codehive.clients.terminal.app import CodehiveApp
from codehive.clients.terminal.ws_client import WSClient

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_PROJECT_ID = str(uuid.uuid4())
_SESSION_ID = str(uuid.uuid4())

MOCK_SESSION = {
    "id": _SESSION_ID,
    "name": "my-session",
    "engine": "native",
    "mode": "execution",
    "status": "executing",
}

MOCK_TASKS = [
    {"id": str(uuid.uuid4()), "title": "Implement auth", "status": "completed"},
    {"id": str(uuid.uuid4()), "title": "Write tests", "status": "running"},
    {"id": str(uuid.uuid4()), "title": "Deploy", "status": "pending"},
]

MOCK_EVENTS = [
    {
        "id": str(uuid.uuid4()),
        "type": "message.created",
        "timestamp": "2026-01-01T10:00:00",
        "data": {"role": "user", "content": "Hello"},
    },
    {
        "id": str(uuid.uuid4()),
        "type": "message.created",
        "timestamp": "2026-01-01T10:01:00",
        "data": {"role": "assistant", "content": "Hi there"},
    },
    {
        "id": str(uuid.uuid4()),
        "type": "tool.call.started",
        "timestamp": "2026-01-01T10:02:00",
        "data": {"tool": "edit_file"},
    },
    {
        "id": str(uuid.uuid4()),
        "type": "message.created",
        "timestamp": "2026-01-01T10:03:00",
        "data": {"role": "system", "content": "File saved"},
    },
]

MOCK_DIFFS = [
    {"path": "src/auth.py", "additions": 42, "deletions": 5},
    {"path": "tests/test_auth.py", "additions": 100, "deletions": 0},
]

MOCK_PROJECTS = [
    {
        "id": _PROJECT_ID,
        "name": "TestProject",
        "path": "/home/test",
        "description": "A test project",
        "created_at": "2026-01-01T00:00:00",
    }
]

MOCK_SESSIONS_FOR_PROJECT = [
    {
        "id": _SESSION_ID,
        "name": "my-session",
        "engine": "native",
        "mode": "execution",
        "status": "executing",
    }
]


def _build_session_mock_api() -> MagicMock:
    """Return a mocked APIClient with session-related data."""
    api = MagicMock(spec=APIClient)
    api.base_url = "http://test:8000"
    api.list_projects.return_value = MOCK_PROJECTS
    api.get_project.return_value = MOCK_PROJECTS[0]
    api.list_sessions.return_value = MOCK_SESSIONS_FOR_PROJECT
    api.list_questions.return_value = []
    api.get_session.return_value = MOCK_SESSION
    api.list_tasks.return_value = MOCK_TASKS
    api.list_events.return_value = MOCK_EVENTS
    api.get_diffs.return_value = MOCK_DIFFS
    api.post_message.return_value = {"id": str(uuid.uuid4()), "status": "ok"}
    return api


def _build_empty_session_mock_api() -> MagicMock:
    """Return a mocked APIClient with empty session data."""
    api = MagicMock(spec=APIClient)
    api.base_url = "http://test:8000"
    api.get_session.return_value = {
        "id": _SESSION_ID,
        "name": "empty-session",
        "engine": "native",
        "mode": "execution",
        "status": "idle",
    }
    api.list_tasks.return_value = []
    api.list_events.return_value = []
    api.get_diffs.return_value = []
    api.post_message.return_value = {"id": str(uuid.uuid4()), "status": "ok"}
    return api


# ---------------------------------------------------------------------------
# Unit: APIClient new methods
# ---------------------------------------------------------------------------


class TestAPIClientSessionMethods:
    def test_get_session(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_SESSION
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        client._client.get.return_value = mock_response

        result = client.get_session(_SESSION_ID)
        assert result == MOCK_SESSION
        client._client.get.assert_called_once_with(f"/api/sessions/{_SESSION_ID}", params=None)

    def test_list_tasks(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TASKS
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        client._client.get.return_value = mock_response

        result = client.list_tasks(_SESSION_ID)
        assert result == MOCK_TASKS
        client._client.get.assert_called_once_with(
            f"/api/sessions/{_SESSION_ID}/tasks", params=None
        )

    def test_list_events(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_EVENTS
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        client._client.get.return_value = mock_response

        result = client.list_events(_SESSION_ID)
        assert result == MOCK_EVENTS
        client._client.get.assert_called_once_with(
            f"/api/sessions/{_SESSION_ID}/events", params=None
        )

    def test_list_events_with_params(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_EVENTS[:2]
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        client._client.get.return_value = mock_response

        result = client.list_events(_SESSION_ID, limit=2, offset=0)
        assert len(result) == 2
        client._client.get.assert_called_once_with(
            f"/api/sessions/{_SESSION_ID}/events",
            params={"limit": 2, "offset": 0},
        )

    def test_get_diffs(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_DIFFS
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        client._client.get.return_value = mock_response

        result = client.get_diffs(_SESSION_ID)
        assert result == MOCK_DIFFS
        client._client.get.assert_called_once_with(
            f"/api/sessions/{_SESSION_ID}/diffs", params=None
        )

    def test_post_message_uses_post(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg-1", "status": "ok"}
        mock_response.raise_for_status = MagicMock()

        client = APIClient("http://localhost:8000")
        client._client = MagicMock()
        client._client.post.return_value = mock_response

        result = client.post_message(_SESSION_ID, "Hello agent")
        assert result == {"id": "msg-1", "status": "ok"}
        client._client.post.assert_called_once_with(
            f"/api/sessions/{_SESSION_ID}/messages",
            json={"content": "Hello agent"},
        )
        # Verify it does NOT use GET
        client._client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Unit: Chat widget
# ---------------------------------------------------------------------------


class TestChatPanel:
    @pytest.mark.asyncio
    async def test_chat_renders_messages(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.chat import ChatMessage, ChatPanel

            panel = app.screen.query_one("#chat-panel", ChatPanel)
            messages = panel.query(ChatMessage)
            # 3 message.created events in MOCK_EVENTS
            assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_chat_shows_role_labels(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.chat import ChatMessage, ChatPanel

            panel = app.screen.query_one("#chat-panel", ChatPanel)
            messages = list(panel.query(ChatMessage))
            # Check that messages contain role text in their rendered content
            first_content = str(getattr(messages[0], "_Static__content", ""))
            assert "user" in first_content

    @pytest.mark.asyncio
    async def test_chat_input_exists_and_focusable(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from textual.widgets import Input

            input_widget = app.screen.query_one("#chat-input", Input)
            assert input_widget is not None
            assert input_widget.focusable is True

    @pytest.mark.asyncio
    async def test_chat_shows_no_messages_when_empty(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_empty_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.chat import _EmptyPlaceholder

            placeholders = app.screen.query(_EmptyPlaceholder)
            assert len(placeholders) >= 1
            content = str(getattr(placeholders[0], "_Static__content", ""))
            assert "No messages" in content


# ---------------------------------------------------------------------------
# Unit: ToDo widget
# ---------------------------------------------------------------------------


class TestTodoPanel:
    @pytest.mark.asyncio
    async def test_todo_renders_tasks(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.todo import TaskRow, TodoPanel

            panel = app.screen.query_one("#todo-panel", TodoPanel)
            rows = panel.query(TaskRow)
            assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_todo_uses_status_indicator(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.status_indicator import StatusIndicator
            from codehive.clients.terminal.widgets.todo import TodoPanel

            panel = app.screen.query_one("#todo-panel", TodoPanel)
            indicators = panel.query(StatusIndicator)
            assert len(indicators) == 3

    @pytest.mark.asyncio
    async def test_todo_shows_no_tasks_when_empty(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_empty_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.todo import _TodoEmpty

            placeholders = app.screen.query(_TodoEmpty)
            assert len(placeholders) >= 1
            content = str(getattr(placeholders[0], "_Static__content", ""))
            assert "No tasks" in content


# ---------------------------------------------------------------------------
# Unit: Timeline widget
# ---------------------------------------------------------------------------


class TestTimelinePanel:
    @pytest.mark.asyncio
    async def test_timeline_renders_events(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.timeline import EventRow, TimelinePanel

            panel = app.screen.query_one("#timeline-panel", TimelinePanel)
            rows = panel.query(EventRow)
            assert len(rows) == 4  # All events

    @pytest.mark.asyncio
    async def test_timeline_chronological_order(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.timeline import EventRow, TimelinePanel

            panel = app.screen.query_one("#timeline-panel", TimelinePanel)
            rows = list(panel.query(EventRow))
            # First event should contain 10:00, last should contain 10:03
            first_content = str(getattr(rows[0], "_Static__content", ""))
            last_content = str(getattr(rows[-1], "_Static__content", ""))
            assert "10:00:00" in first_content
            assert "10:03:00" in last_content

    @pytest.mark.asyncio
    async def test_timeline_shows_no_events_when_empty(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_empty_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.timeline import _TimelineEmpty

            placeholders = app.screen.query(_TimelineEmpty)
            assert len(placeholders) >= 1
            content = str(getattr(placeholders[0], "_Static__content", ""))
            assert "No events" in content


# ---------------------------------------------------------------------------
# Unit: Changed Files widget
# ---------------------------------------------------------------------------


class TestFilesPanel:
    @pytest.mark.asyncio
    async def test_files_renders_diffs(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.files import FileRow, FilesPanel

            panel = app.screen.query_one("#files-panel", FilesPanel)
            rows = panel.query(FileRow)
            assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_files_shows_no_changes_when_empty(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_empty_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.files import _FilesEmpty

            placeholders = app.screen.query(_FilesEmpty)
            assert len(placeholders) >= 1
            content = str(getattr(placeholders[0], "_Static__content", ""))
            assert "No changes" in content


# ---------------------------------------------------------------------------
# Unit: Session screen composition
# ---------------------------------------------------------------------------


class TestSessionScreen:
    @pytest.mark.asyncio
    async def test_session_screen_composes_with_all_panels(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.chat import ChatPanel
            from codehive.clients.terminal.widgets.files import FilesPanel
            from codehive.clients.terminal.widgets.timeline import TimelinePanel
            from codehive.clients.terminal.widgets.todo import TodoPanel

            assert app.screen.query_one("#chat-panel", ChatPanel)
            assert app.screen.query_one("#todo-panel", TodoPanel)
            assert app.screen.query_one("#timeline-panel", TimelinePanel)
            assert app.screen.query_one("#files-panel", FilesPanel)

    @pytest.mark.asyncio
    async def test_session_screen_fetches_data_on_mount(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        mock_api = _build_session_mock_api()
        app.api_client = mock_api  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            mock_api.get_session.assert_called_with(_SESSION_ID)
            mock_api.list_tasks.assert_called_with(_SESSION_ID)
            mock_api.list_events.assert_called_with(_SESSION_ID)
            mock_api.get_diffs.assert_called_with(_SESSION_ID)

    @pytest.mark.asyncio
    async def test_session_screen_populates_all_panels(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.chat import ChatMessage
            from codehive.clients.terminal.widgets.files import FileRow
            from codehive.clients.terminal.widgets.timeline import EventRow
            from codehive.clients.terminal.widgets.todo import TaskRow

            assert len(app.screen.query(ChatMessage)) == 3
            assert len(app.screen.query(TaskRow)) == 3
            assert len(app.screen.query(EventRow)) == 4
            assert len(app.screen.query(FileRow)) == 2

    @pytest.mark.asyncio
    async def test_session_screen_escape_pops_back(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.dashboard import DashboardScreen
            from codehive.clients.terminal.screens.session import SessionScreen

            app.push_screen(SessionScreen(_SESSION_ID))
            await pilot.pause()
            assert isinstance(app.screen, SessionScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)


# ---------------------------------------------------------------------------
# Unit: WebSocket client
# ---------------------------------------------------------------------------


class TestWSClient:
    def test_instantiation(self) -> None:
        ws = WSClient("http://localhost:8000", _SESSION_ID)
        assert ws._session_id == _SESSION_ID

    def test_ws_url_from_http(self) -> None:
        ws = WSClient("http://localhost:8000", _SESSION_ID)
        assert ws.ws_url == f"ws://localhost:8000/api/sessions/{_SESSION_ID}/ws"

    def test_ws_url_from_https(self) -> None:
        ws = WSClient("https://example.com", _SESSION_ID)
        assert ws.ws_url == f"wss://example.com/api/sessions/{_SESSION_ID}/ws"

    def test_ws_url_strips_trailing_slash(self) -> None:
        ws = WSClient("http://localhost:8000/", _SESSION_ID)
        assert ws.ws_url == f"ws://localhost:8000/api/sessions/{_SESSION_ID}/ws"

    def test_dispatches_events_via_callback(self) -> None:
        """WSClient calls the callback for each received JSON message."""
        ws = WSClient("http://localhost:8000", _SESSION_ID)
        callback = MagicMock()

        # Mock the websocket connection
        mock_conn = MagicMock()
        received_messages = [
            '{"type": "message.created", "data": {}}',
            '{"type": "task.started", "data": {}}',
        ]
        call_count = 0

        def fake_recv(timeout: float = 1.0) -> str:
            nonlocal call_count
            if call_count < len(received_messages):
                msg = received_messages[call_count]
                call_count += 1
                return msg
            ws.stop()
            raise TimeoutError()

        mock_conn.recv = fake_recv
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        import codehive.clients.terminal.ws_client as ws_mod

        original_connect = ws_mod.ws_sync.connect

        def mock_ws_connect(url: str) -> MagicMock:
            return mock_conn

        ws_mod.ws_sync.connect = mock_ws_connect  # type: ignore[assignment]
        try:
            ws.connect(callback)
        finally:
            ws_mod.ws_sync.connect = original_connect  # type: ignore[assignment]

        assert callback.call_count == 2
        callback.assert_any_call({"type": "message.created", "data": {}})
        callback.assert_any_call({"type": "task.started", "data": {}})


# ---------------------------------------------------------------------------
# Integration: Navigation flow
# ---------------------------------------------------------------------------


class TestNavigationFlow:
    @pytest.mark.asyncio
    async def test_project_detail_session_select_pushes_session_screen(self) -> None:
        app = CodehiveApp(base_url="http://test:8000")
        app.api_client = _build_session_mock_api()  # type: ignore[assignment]
        async with app.run_test(size=(120, 40)) as pilot:
            from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

            app.push_screen(ProjectDetailScreen(_PROJECT_ID))
            await pilot.pause()

            from codehive.clients.terminal.widgets.data_table import StyledDataTable

            table = app.screen.query_one("#pd-table", StyledDataTable)
            table.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.pause()

            from codehive.clients.terminal.screens.session import SessionScreen

            assert isinstance(app.screen, SessionScreen)
            assert app.screen.session_id == _SESSION_ID
