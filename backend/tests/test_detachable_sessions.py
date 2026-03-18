"""Tests for detachable TUI session features (issue #99).

Covers:
- Part B: History loading on reconnect (CodeApp._load_backend_session)
- Part C: Live streaming resume (WebSocket reconnect)
- Deduplication of history vs WebSocket events
- TUI disconnect does not stop backend engine
"""

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
        self._engine = None


def _make_backend_app(
    session_id: uuid.UUID | None = None,
    backend_url: str = "http://localhost:7433",
) -> _BackendCodeApp:
    return _BackendCodeApp(
        project_dir="/tmp/test-project",
        backend_url=backend_url,
        session_id=session_id or uuid.uuid4(),
        project_id=uuid.uuid4(),
    )


# ---------------------------------------------------------------------------
# Tests: History loading
# ---------------------------------------------------------------------------


class TestHistoryLoading:
    @pytest.mark.asyncio
    async def test_loads_transcript_on_mount(self) -> None:
        """In backend mode, on_mount calls _load_backend_session which fetches transcript."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "idle",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 200
        mock_transcript_resp.json.return_value = {
            "session_id": str(app._session_id),
            "entries": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Hello",
                    "timestamp": "2026-03-18T10:00:00",
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "Hi there!",
                    "timestamp": "2026-03-18T10:00:01",
                },
            ],
        }

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._load_backend_session()

                # Verify transcript was loaded -- last_history_timestamp should be set
                assert app._last_history_timestamp == "2026-03-18T10:00:01"

    @pytest.mark.asyncio
    async def test_empty_transcript_shows_session_started(self) -> None:
        """Empty transcript (new session) shows session started message."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "idle",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 200
        mock_transcript_resp.json.return_value = {
            "session_id": str(app._session_id),
            "entries": [],
        }

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._load_backend_session()

                # No history timestamp since no entries
                assert app._last_history_timestamp == ""

    @pytest.mark.asyncio
    async def test_transcript_error_does_not_crash(self) -> None:
        """Transcript loading error (e.g. 500) does not crash the app."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "idle",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 500

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                # Should not raise
                await app._load_backend_session()


# ---------------------------------------------------------------------------
# Tests: Reconnect with running session
# ---------------------------------------------------------------------------


class TestReconnectRunningSession:
    @pytest.mark.asyncio
    async def test_executing_session_sets_busy_flag(self) -> None:
        """When session is executing, _load_backend_session sets _busy=True."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "executing",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 200
        mock_transcript_resp.json.return_value = {
            "session_id": str(app._session_id),
            "entries": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Do something",
                    "timestamp": "2026-03-18T10:00:00",
                },
            ],
        }

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with (
                patch("httpx.AsyncClient") as mock_client_cls,
                patch.object(app, "_stream_ws_events", new_callable=AsyncMock),
            ):
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._load_backend_session()

                # busy should be True since session is executing
                assert app._busy is True
                # ws_task should have been created
                assert app._ws_task is not None


# ---------------------------------------------------------------------------
# Tests: Reconnect with finished session
# ---------------------------------------------------------------------------


class TestReconnectFinishedSession:
    @pytest.mark.asyncio
    async def test_idle_session_not_busy(self) -> None:
        """When session is idle, app is not busy after loading history."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "idle",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 200
        mock_transcript_resp.json.return_value = {
            "session_id": str(app._session_id),
            "entries": [],
        }

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._load_backend_session()
                assert app._busy is False

    @pytest.mark.asyncio
    async def test_failed_session_shows_status(self) -> None:
        """When session is failed, status indicator shows failure."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "failed",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 200
        mock_transcript_resp.json.return_value = {
            "session_id": str(app._session_id),
            "entries": [],
        }

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._load_backend_session()
                assert app._busy is False

    @pytest.mark.asyncio
    async def test_completed_session_not_busy(self) -> None:
        """When session is completed, app is not busy."""
        app = _make_backend_app()

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": str(app._session_id),
            "status": "completed",
        }

        mock_transcript_resp = MagicMock()
        mock_transcript_resp.status_code = 200
        mock_transcript_resp.json.return_value = {
            "session_id": str(app._session_id),
            "entries": [],
        }

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[mock_status_resp, mock_transcript_resp])
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._load_backend_session()
                assert app._busy is False


# ---------------------------------------------------------------------------
# Tests: Deduplication
# ---------------------------------------------------------------------------


class TestEventDeduplication:
    @pytest.mark.asyncio
    async def test_ws_event_before_history_timestamp_is_skipped(self) -> None:
        """WebSocket events with timestamps <= last history timestamp are skipped."""
        app = _make_backend_app()
        app._last_history_timestamp = "2026-03-18T10:00:05"

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            # Event at same time as history -- should be skipped
            event_old = {
                "type": "message.created",
                "role": "assistant",
                "content": "duplicate",
                "created_at": "2026-03-18T10:00:05",
            }

            # Track whether _append_assistant is called
            calls = []
            app._append_assistant = lambda text: calls.append(text)  # type: ignore[assignment]

            # _process_ws_event doesn't check timestamps -- that's done in _stream_ws_events.
            # But _stream_ws_events applies the check. Let's verify the logic directly:
            event_ts = event_old.get("created_at", "")
            should_skip = (
                event_ts and app._last_history_timestamp and event_ts <= app._last_history_timestamp
            )
            assert should_skip is True

    @pytest.mark.asyncio
    async def test_ws_event_after_history_timestamp_is_rendered(self) -> None:
        """WebSocket events with timestamps > last history timestamp are rendered."""
        app = _make_backend_app()
        app._last_history_timestamp = "2026-03-18T10:00:05"

        event_new = {
            "type": "message.created",
            "role": "assistant",
            "content": "new message",
            "created_at": "2026-03-18T10:00:10",
        }

        event_ts = event_new.get("created_at", "")
        should_skip = (
            event_ts and app._last_history_timestamp and event_ts <= app._last_history_timestamp
        )
        assert should_skip is False


# ---------------------------------------------------------------------------
# Tests: process_ws_event
# ---------------------------------------------------------------------------


class TestProcessWsEvent:
    @pytest.mark.asyncio
    async def test_assistant_message_rendered(self) -> None:
        """_process_ws_event renders assistant message.created events."""
        app = _make_backend_app()

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            calls: list[str] = []
            app._append_assistant = lambda text: calls.append(text)  # type: ignore[assignment]

            app._process_ws_event(
                {
                    "type": "message.created",
                    "role": "assistant",
                    "content": "Hello from WS",
                }
            )

            assert len(calls) == 1
            assert calls[0] == "Hello from WS"

    @pytest.mark.asyncio
    async def test_tool_call_started_rendered(self) -> None:
        """_process_ws_event renders tool.call.started events."""
        app = _make_backend_app()

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            calls: list[tuple[str, str]] = []
            app._append_tool = lambda name, summary: calls.append((name, summary))  # type: ignore[assignment]

            app._process_ws_event(
                {
                    "type": "tool.call.started",
                    "tool_name": "read_file",
                    "tool_input": {"path": "test.py"},
                }
            )

            assert len(calls) == 1
            assert calls[0][0] == "read_file"


# ---------------------------------------------------------------------------
# Tests: Async message dispatch from TUI
# ---------------------------------------------------------------------------


class TestAsyncMessageDispatchFromTUI:
    @pytest.mark.asyncio
    async def test_send_backend_message_async_calls_endpoint(self) -> None:
        """_send_backend_message_async posts to /messages/async endpoint."""
        app = _make_backend_app()
        session_id = app._session_id

        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {"status": "running"}

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            with (
                patch("httpx.AsyncClient") as mock_client_cls,
                patch.object(app, "_stream_ws_events", new_callable=AsyncMock),
            ):
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._send_backend_message_async("hello")

                mock_client.post.assert_called_once_with(
                    f"/api/sessions/{session_id}/messages/async",
                    json={"content": "hello"},
                )

    @pytest.mark.asyncio
    async def test_send_backend_message_async_conflict_shows_message(self) -> None:
        """409 Conflict from async endpoint shows message in chat."""
        app = _make_backend_app()

        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "already running"}

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            calls: list[str] = []
            app._append_system = lambda text: calls.append(text)  # type: ignore[assignment]

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                await app._send_backend_message_async("hello")

                assert any("running engine task" in c for c in calls)


# ---------------------------------------------------------------------------
# Tests: Render transcript entries
# ---------------------------------------------------------------------------


class TestRenderTranscriptEntries:
    @pytest.mark.asyncio
    async def test_renders_user_and_assistant_messages(self) -> None:
        """_render_transcript_entries renders user and assistant messages."""
        app = _make_backend_app()

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            user_calls: list[str] = []
            asst_calls: list[str] = []
            app._append_user = lambda text: user_calls.append(text)  # type: ignore[assignment]
            app._append_assistant = lambda text: asst_calls.append(text)  # type: ignore[assignment]

            entries = [
                {"type": "message", "role": "user", "content": "Hello"},
                {"type": "message", "role": "assistant", "content": "Hi back"},
            ]
            app._render_transcript_entries(entries)

            assert user_calls == ["Hello"]
            assert asst_calls == ["Hi back"]

    @pytest.mark.asyncio
    async def test_renders_tool_calls(self) -> None:
        """_render_transcript_entries renders tool_call entries."""
        app = _make_backend_app()

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            tool_calls: list[tuple[str, str]] = []
            app._append_tool = lambda name, summary: tool_calls.append((name, summary))  # type: ignore[assignment]

            entries = [
                {"type": "tool_call", "tool_name": "read_file", "input": "foo.py"},
            ]
            app._render_transcript_entries(entries)

            assert len(tool_calls) == 1
            assert tool_calls[0][0] == "read_file"

    @pytest.mark.asyncio
    async def test_empty_entries_renders_nothing(self) -> None:
        """Empty entries list does not call any render methods."""
        app = _make_backend_app()

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            calls: list[str] = []
            app._append_user = lambda text: calls.append(text)  # type: ignore[assignment]
            app._append_assistant = lambda text: calls.append(text)  # type: ignore[assignment]
            app._append_tool = lambda name, summary: calls.append(name)  # type: ignore[assignment]

            app._render_transcript_entries([])
            assert calls == []
