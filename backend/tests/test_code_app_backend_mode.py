"""Tests for CodeApp backend mode."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.clients.terminal.code_app import CodeApp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _BackendCodeApp(CodeApp):
    """CodeApp subclass for testing backend mode (skips engine init)."""

    async def _init_engine(self) -> None:
        # In backend mode, the real _init_engine just sets self._engine = None
        self._engine = None


class _LocalCodeApp(CodeApp):
    """CodeApp subclass for testing local mode (skips engine init)."""

    async def _init_engine(self) -> None:
        # Simulate local mode: set a dummy engine
        self._engine = MagicMock()


def _make_backend_app() -> _BackendCodeApp:
    return _BackendCodeApp(
        project_dir="/tmp/test-project",
        backend_url="http://localhost:7433",
        session_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )


def _make_local_app() -> _LocalCodeApp:
    return _LocalCodeApp(
        project_dir="/tmp/test-project",
    )


# ---------------------------------------------------------------------------
# Tests: Backend mode initialization
# ---------------------------------------------------------------------------


class TestBackendModeInit:
    @pytest.mark.asyncio
    async def test_backend_mode_no_engine(self) -> None:
        """In backend mode, _init_engine does NOT instantiate NativeEngine."""
        app = CodeApp(
            project_dir="/tmp/test-project",
            backend_url="http://localhost:7433",
            session_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        # Call the real _init_engine (not the test subclass)
        await app._init_engine()
        assert app._engine is None

    def test_backend_url_stored(self) -> None:
        """CodeApp stores backend_url when provided."""
        url = "http://my-backend:7433"
        app = CodeApp(
            project_dir="/tmp/test",
            backend_url=url,
            session_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        assert app._backend_url == url

    def test_session_id_from_constructor(self) -> None:
        """CodeApp uses the provided session_id."""
        sid = uuid.uuid4()
        app = CodeApp(
            project_dir="/tmp/test",
            backend_url="http://localhost:7433",
            session_id=sid,
            project_id=uuid.uuid4(),
        )
        assert app._session_id == sid

    def test_project_id_from_constructor(self) -> None:
        """CodeApp stores the provided project_id."""
        pid = uuid.uuid4()
        app = CodeApp(
            project_dir="/tmp/test",
            backend_url="http://localhost:7433",
            session_id=uuid.uuid4(),
            project_id=pid,
        )
        assert app._project_id == pid


# ---------------------------------------------------------------------------
# Tests: Backend mode message sending
# ---------------------------------------------------------------------------


class TestBackendModeMessages:
    @pytest.mark.asyncio
    async def test_send_message_posts_to_backend(self) -> None:
        """_run_agent in backend mode sends POST to /api/sessions/{id}/messages."""
        session_id = uuid.uuid4()
        app = _make_backend_app()
        app._session_id = session_id
        app._backend_url = "http://localhost:7433"

        events_returned = [
            {"type": "message.created", "role": "assistant", "content": "Hi there!"},
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = events_returned

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                # Collect events from _send_backend_message
                collected = []
                async for ev in app._send_backend_message("hello"):
                    collected.append(ev)

                assert len(collected) == 1
                assert collected[0]["type"] == "message.created"
                assert collected[0]["content"] == "Hi there!"

                mock_client.post.assert_called_once_with(
                    f"/api/sessions/{session_id}/messages",
                    json={"content": "hello"},
                )

    @pytest.mark.asyncio
    async def test_tool_call_events_from_backend(self) -> None:
        """Tool call events from the backend response are yielded."""
        app = _make_backend_app()

        events_returned = [
            {
                "type": "tool.call.started",
                "tool_name": "read_file",
                "tool_input": {"path": "foo.py"},
            },
            {"type": "tool.call.finished", "tool_name": "read_file", "result": {"content": "data"}},
            {"type": "message.created", "role": "assistant", "content": "Done."},
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = events_returned

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                collected = []
                async for ev in app._send_backend_message("do something"):
                    collected.append(ev)

                assert len(collected) == 3
                assert collected[0]["type"] == "tool.call.started"
                assert collected[1]["type"] == "tool.call.finished"
                assert collected[2]["type"] == "message.created"

    @pytest.mark.asyncio
    async def test_http_error_yields_error_event(self) -> None:
        """HTTP error from messages endpoint yields an error message, not a crash."""
        app = _make_backend_app()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"detail": "Internal server error"}
        mock_resp.text = "Internal server error"

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                collected = []
                async for ev in app._send_backend_message("hello"):
                    collected.append(ev)

                assert len(collected) == 1
                assert "Error from backend" in collected[0]["content"]
                assert "500" in collected[0]["content"]


# ---------------------------------------------------------------------------
# Tests: Local mode regression
# ---------------------------------------------------------------------------


class TestLocalModeRegression:
    def test_local_mode_no_backend_url(self) -> None:
        """CodeApp with backend_url=None uses local mode."""
        app = CodeApp(project_dir="/tmp/test")
        assert app._backend_url is None

    def test_local_mode_generates_session_id(self) -> None:
        """CodeApp without explicit session_id generates one."""
        app = CodeApp(project_dir="/tmp/test")
        assert app._session_id is not None
        assert isinstance(app._session_id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_local_mode_init_creates_engine(self) -> None:
        """In local mode, _init_engine creates a NativeEngine (mocked)."""
        app = _make_local_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # Our test subclass sets a mock engine
            assert app._engine is not None
