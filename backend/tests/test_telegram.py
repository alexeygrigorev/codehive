"""Tests for Telegram bot commands with mocked httpx and mocked Telegram Updates."""

from __future__ import annotations

import uuid
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from telegram.ext import CommandHandler

from codehive.clients.telegram.bot import COMMAND_HANDLERS, create_bot
from codehive.clients.telegram.formatters import (
    format_project_list,
    format_question_list,
    format_session_status,
    format_task_list,
)
from codehive.clients.telegram.handlers import (
    answer_handler,
    approve_handler,
    projects_handler,
    questions_handler,
    reject_handler,
    send_handler,
    sessions_handler,
    start_handler,
    status_handler,
    stop_handler,
    todo_handler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update() -> MagicMock:
    """Create a mocked Telegram Update with a message that has reply_text."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _make_context(
    args: list[str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> MagicMock:
    """Create a mocked context with args and bot_data containing http_client."""
    context = MagicMock()
    context.args = args or []
    if http_client is None:
        http_client = MagicMock(spec=httpx.AsyncClient)
    context.bot_data = {"http_client": http_client}
    return context


def _mock_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = str(json_data)
    return resp


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestFormatProjectList:
    def test_formats_projects(self) -> None:
        projects = [
            {"id": "abc-123", "name": "My Project"},
            {"id": "def-456", "name": "Other Project"},
        ]
        result = format_project_list(projects)
        assert "My Project" in result
        assert "abc-123" in result
        assert "Other Project" in result
        assert "def-456" in result

    def test_empty_list(self) -> None:
        result = format_project_list([])
        assert result == "No projects found."


class TestFormatSessionStatus:
    def test_formats_session(self) -> None:
        session = {
            "id": "sess-1",
            "name": "coding-session",
            "engine": "native",
            "mode": "execution",
            "status": "idle",
            "created_at": "2026-01-01T00:00:00",
        }
        result = format_session_status(session)
        assert "coding-session" in result
        assert "native" in result
        assert "execution" in result
        assert "idle" in result


class TestFormatTaskList:
    def test_formats_tasks(self) -> None:
        tasks = [
            {"title": "Write tests", "status": "done"},
            {"title": "Fix bug", "status": "pending"},
            {"title": "Deploy", "status": "running"},
        ]
        result = format_task_list(tasks)
        assert "[x] Write tests" in result
        assert "[ ] Fix bug" in result
        assert "[~] Deploy" in result

    def test_empty_tasks(self) -> None:
        result = format_task_list([])
        assert result == "No tasks found."


class TestFormatQuestionList:
    def test_formats_questions(self) -> None:
        questions = [
            {"id": "q1", "text": "Which DB to use?", "session_id": "s1"},
            {"id": "q2", "question": "What framework?", "session_id": "s2"},
        ]
        result = format_question_list(questions)
        assert "q1" in result
        assert "Which DB to use?" in result
        assert "q2" in result
        assert "What framework?" in result

    def test_empty_questions(self) -> None:
        result = format_question_list([])
        assert result == "No unanswered questions."


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestStartHandler:
    @pytest.mark.asyncio
    async def test_replies_with_commands(self) -> None:
        update = _make_update()
        context = _make_context()
        await start_handler(update, context)
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Welcome to Codehive" in reply_text
        assert "/projects" in reply_text
        assert "/sessions" in reply_text
        assert "/status" in reply_text
        assert "/todo" in reply_text
        assert "/send" in reply_text
        assert "/approve" in reply_text
        assert "/reject" in reply_text
        assert "/questions" in reply_text
        assert "/answer" in reply_text
        assert "/stop" in reply_text


class TestProjectsHandler:
    @pytest.mark.asyncio
    async def test_lists_projects(self) -> None:
        projects = [{"id": "p1", "name": "Project One"}]
        mock_resp = _mock_response(200, projects)

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(http_client=http_client)
        await projects_handler(update, context)

        http_client.get.assert_called_once_with("/api/projects")
        reply = update.message.reply_text.call_args[0][0]
        assert "Project One" in reply


class TestSessionsHandler:
    @pytest.mark.asyncio
    async def test_lists_sessions(self) -> None:
        pid = str(uuid.uuid4())
        sessions = [{"id": "s1", "name": "Session One", "status": "idle", "engine": "native"}]
        mock_resp = _mock_response(200, sessions)

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[pid], http_client=http_client)
        await sessions_handler(update, context)

        http_client.get.assert_called_once_with(f"/api/projects/{pid}/sessions")
        reply = update.message.reply_text.call_args[0][0]
        assert "Session One" in reply

    @pytest.mark.asyncio
    async def test_missing_arg_shows_usage(self) -> None:
        update = _make_update()
        context = _make_context(args=[])
        await sessions_handler(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply


class TestStatusHandler:
    @pytest.mark.asyncio
    async def test_shows_status(self) -> None:
        sid = str(uuid.uuid4())
        session = {
            "id": sid,
            "name": "test-session",
            "engine": "native",
            "mode": "execution",
            "status": "idle",
            "created_at": "2026-01-01T00:00:00",
        }
        mock_resp = _mock_response(200, session)

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[sid], http_client=http_client)
        await status_handler(update, context)

        http_client.get.assert_called_once_with(f"/api/sessions/{sid}")
        reply = update.message.reply_text.call_args[0][0]
        assert "test-session" in reply
        assert "idle" in reply

    @pytest.mark.asyncio
    async def test_missing_arg_shows_usage(self) -> None:
        update = _make_update()
        context = _make_context(args=[])
        await status_handler(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply


class TestTodoHandler:
    @pytest.mark.asyncio
    async def test_lists_tasks(self) -> None:
        sid = str(uuid.uuid4())
        tasks = [
            {"title": "Task A", "status": "done"},
            {"title": "Task B", "status": "pending"},
        ]
        mock_resp = _mock_response(200, tasks)

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[sid], http_client=http_client)
        await todo_handler(update, context)

        http_client.get.assert_called_once_with(f"/api/sessions/{sid}/tasks")
        reply = update.message.reply_text.call_args[0][0]
        assert "Task A" in reply
        assert "Task B" in reply


class TestSendHandler:
    @pytest.mark.asyncio
    async def test_sends_message(self) -> None:
        sid = str(uuid.uuid4())
        events = [
            {"type": "message.created", "role": "user", "content": "hello"},
            {"type": "message.created", "role": "assistant", "content": "Hi there!"},
        ]
        mock_resp = _mock_response(200, events)

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[sid, "hello", "world"], http_client=http_client)
        await send_handler(update, context)

        http_client.post.assert_called_once_with(
            f"/api/sessions/{sid}/messages", json={"content": "hello world"}
        )
        reply = update.message.reply_text.call_args[0][0]
        assert "Hi there!" in reply

    @pytest.mark.asyncio
    async def test_missing_args_shows_usage(self) -> None:
        update = _make_update()
        context = _make_context(args=[])
        await send_handler(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply

    @pytest.mark.asyncio
    async def test_missing_message_shows_usage(self) -> None:
        update = _make_update()
        context = _make_context(args=["session-id-only"])
        await send_handler(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply


class TestApproveHandler:
    @pytest.mark.asyncio
    async def test_approves(self) -> None:
        action_id = str(uuid.uuid4())
        mock_resp = _mock_response(200, {"status": "approved"})

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[action_id], http_client=http_client)
        await approve_handler(update, context)

        http_client.post.assert_called_once_with(f"/api/sessions/{action_id}/approve")
        reply = update.message.reply_text.call_args[0][0]
        assert "Approved" in reply


class TestRejectHandler:
    @pytest.mark.asyncio
    async def test_rejects(self) -> None:
        action_id = str(uuid.uuid4())
        mock_resp = _mock_response(200, {"status": "rejected"})

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[action_id], http_client=http_client)
        await reject_handler(update, context)

        http_client.post.assert_called_once_with(f"/api/sessions/{action_id}/reject")
        reply = update.message.reply_text.call_args[0][0]
        assert "Rejected" in reply


class TestQuestionsHandler:
    @pytest.mark.asyncio
    async def test_lists_questions(self) -> None:
        sid = str(uuid.uuid4())
        questions = [
            {"id": "q1", "text": "Which DB?", "session_id": sid},
        ]
        mock_resp = _mock_response(200, questions)

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[sid], http_client=http_client)
        await questions_handler(update, context)

        http_client.get.assert_called_once_with(
            f"/api/sessions/{sid}/questions", params={"answered": "false"}
        )
        reply = update.message.reply_text.call_args[0][0]
        assert "Which DB?" in reply


class TestAnswerHandler:
    @pytest.mark.asyncio
    async def test_answers_question(self) -> None:
        qid = str(uuid.uuid4())
        mock_resp = _mock_response(200, {"status": "answered"})

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[qid, "Use", "PostgreSQL"], http_client=http_client)
        await answer_handler(update, context)

        http_client.post.assert_called_once_with(
            f"/api/questions/{qid}/answer", json={"text": "Use PostgreSQL"}
        )
        reply = update.message.reply_text.call_args[0][0]
        assert "Answer submitted" in reply

    @pytest.mark.asyncio
    async def test_missing_args_shows_usage(self) -> None:
        update = _make_update()
        context = _make_context(args=[])
        await answer_handler(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply


class TestStopHandler:
    @pytest.mark.asyncio
    async def test_stops_session(self) -> None:
        sid = str(uuid.uuid4())
        mock_resp = _mock_response(200, {"status": "paused"})

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[sid], http_client=http_client)
        await stop_handler(update, context)

        http_client.post.assert_called_once_with(f"/api/sessions/{sid}/pause")
        reply = update.message.reply_text.call_args[0][0]
        assert "Session stopped" in reply

    @pytest.mark.asyncio
    async def test_missing_arg_shows_usage(self) -> None:
        update = _make_update()
        context = _make_context(args=[])
        await stop_handler(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_404_shows_not_found(self) -> None:
        sid = str(uuid.uuid4())
        mock_resp = _mock_response(404, {"detail": "Session not found"})

        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(return_value=mock_resp)

        update = _make_update()
        context = _make_context(args=[sid], http_client=http_client)
        await status_handler(update, context)

        reply = update.message.reply_text.call_args[0][0]
        assert "Not found" in reply
        assert "Session not found" in reply

    @pytest.mark.asyncio
    async def test_connection_error_shows_message(self) -> None:
        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        update = _make_update()
        context = _make_context(http_client=http_client)
        await projects_handler(update, context)

        reply = update.message.reply_text.call_args[0][0]
        assert "Cannot reach server" in reply


# ---------------------------------------------------------------------------
# Bot setup tests
# ---------------------------------------------------------------------------


class TestBotSetup:
    def test_create_bot_registers_all_commands(self) -> None:
        with patch("codehive.clients.telegram.bot.Application") as mock_app_cls:
            mock_app = MagicMock()
            mock_builder = MagicMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = mock_app
            mock_app.bot_data = {}
            mock_app_cls.builder.return_value = mock_builder

            create_bot(token="test-token", base_url="http://localhost:7433")

            # Verify all 11 command handlers + 1 callback query handler
            assert mock_app.add_handler.call_count == 12
            registered = set()
            for call in mock_app.add_handler.call_args_list:
                handler = call[0][0]
                if isinstance(handler, CommandHandler):
                    for cmd in handler.commands:
                        registered.add(cmd)
            expected = {
                "start",
                "projects",
                "sessions",
                "status",
                "todo",
                "send",
                "approve",
                "reject",
                "questions",
                "answer",
                "stop",
            }
            assert registered == expected

    def test_command_handlers_dict_has_all_commands(self) -> None:
        expected = {
            "start",
            "projects",
            "sessions",
            "status",
            "todo",
            "send",
            "approve",
            "reject",
            "questions",
            "answer",
            "stop",
        }
        assert set(COMMAND_HANDLERS.keys()) == expected


class TestTelegramCLI:
    def test_telegram_subcommand_missing_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """codehive telegram without token prints error."""
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive", "telegram"])
        monkeypatch.delenv("CODEHIVE_TELEGRAM_BOT_TOKEN", raising=False)
        out = StringIO()
        err = StringIO()
        monkeypatch.setattr("sys.stdout", out)
        monkeypatch.setattr("sys.stderr", err)
        try:
            main()
        except SystemExit:
            pass
        output = out.getvalue() + err.getvalue()
        assert "CODEHIVE_TELEGRAM_BOT_TOKEN" in output

    def test_telegram_subcommand_with_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """codehive telegram with token calls create_bot and run_polling."""
        from codehive.cli import main

        monkeypatch.setattr("sys.argv", ["codehive", "telegram"])
        monkeypatch.setenv("CODEHIVE_TELEGRAM_BOT_TOKEN", "fake-token-123")

        mock_app = MagicMock()
        with patch(
            "codehive.clients.telegram.bot.create_bot", return_value=mock_app
        ) as mock_create:
            main()
            mock_create.assert_called_once_with(
                token="fake-token-123", base_url="http://127.0.0.1:7433"
            )
            mock_app.run_polling.assert_called_once()
