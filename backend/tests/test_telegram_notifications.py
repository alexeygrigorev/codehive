"""Tests for Telegram push notifications and inline approval callbacks."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from telegram import InlineKeyboardMarkup

from codehive.clients.telegram.formatters import (
    format_approval_notification,
    format_question_notification,
    format_session_completed_notification,
    format_session_failed_notification,
    format_subagent_report_notification,
)
from codehive.clients.telegram.handlers import callback_query_handler
from codehive.clients.telegram.notifications import NotificationDispatcher
from codehive.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: object) -> Settings:
    """Create a Settings instance with notification defaults and overrides."""
    defaults = {
        "telegram_chat_id": "12345",
        "telegram_bot_token": "fake-token",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _make_event(event_type: str, data: dict) -> str:
    """Serialise a fake event to JSON as the event bus would."""
    return json.dumps(
        {
            "id": "evt-1",
            "session_id": "sess-1",
            "type": event_type,
            "data": data,
            "created_at": "2026-03-15T12:00:00",
        }
    )


def _make_pubsub_message(event_type: str, data: dict) -> dict:
    """Build a dict mimicking a Redis pub/sub pmessage."""
    return {
        "type": "pmessage",
        "pattern": b"session:*:events",
        "channel": b"session:sess-1:events",
        "data": _make_event(event_type, data).encode("utf-8"),
    }


def _make_update_with_callback(callback_data: str) -> MagicMock:
    """Create a mocked Telegram Update with a callback_query."""
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.data = callback_data
    return update


def _make_context(http_client: httpx.AsyncClient | None = None) -> MagicMock:
    context = MagicMock()
    if http_client is None:
        http_client = AsyncMock(spec=httpx.AsyncClient)
    context.bot_data = {"http_client": http_client}
    return context


def _mock_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = str(json_data)
    return resp


# ---------------------------------------------------------------------------
# Notification formatter tests
# ---------------------------------------------------------------------------


class TestFormatApprovalNotification:
    def test_returns_text_and_markup(self) -> None:
        data = {
            "session_name": "deploy-session",
            "action_description": "Delete production DB",
            "action_id": "act-42",
        }
        text, markup = format_approval_notification(data)
        assert "deploy-session" in text
        assert "Delete production DB" in text
        assert "act-42" in text
        assert isinstance(markup, InlineKeyboardMarkup)
        buttons = markup.inline_keyboard[0]
        assert len(buttons) == 2
        assert buttons[0].text == "Approve"
        assert buttons[0].callback_data == "approve:act-42"
        assert buttons[1].text == "Reject"
        assert buttons[1].callback_data == "reject:act-42"


class TestFormatSessionCompletedNotification:
    def test_contains_session_name(self) -> None:
        text = format_session_completed_notification(
            {"session_name": "build-session", "summary": "All tests pass"}
        )
        assert "build-session" in text
        assert "All tests pass" in text


class TestFormatSessionFailedNotification:
    def test_contains_session_name_and_error(self) -> None:
        text = format_session_failed_notification(
            {"session_name": "ci-session", "error": "OOM killed"}
        )
        assert "ci-session" in text
        assert "OOM killed" in text


class TestFormatQuestionNotification:
    def test_contains_question_text_and_session(self) -> None:
        text = format_question_notification(
            {
                "session_name": "planning-session",
                "question_text": "Which DB should we use?",
                "question_id": "q-7",
            }
        )
        assert "planning-session" in text
        assert "Which DB should we use?" in text
        assert "q-7" in text


class TestFormatSubagentReportNotification:
    def test_contains_subagent_info(self) -> None:
        text = format_subagent_report_notification(
            {
                "parent_session": "orchestrator-1",
                "subagent_name": "backend-agent",
                "status": "completed",
            }
        )
        assert "orchestrator-1" in text
        assert "backend-agent" in text
        assert "completed" in text


# ---------------------------------------------------------------------------
# NotificationDispatcher unit tests
# ---------------------------------------------------------------------------


class TestNotificationDispatcher:
    @pytest.mark.asyncio
    async def test_session_completed_sends_message(self) -> None:
        bot = AsyncMock()
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message(
            "session.completed", {"session_name": "my-session", "summary": "done"}
        )
        await dispatcher._handle_message(msg)

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args
        assert call_kwargs.kwargs["chat_id"] == "12345"
        assert "my-session" in call_kwargs.kwargs["text"]

    @pytest.mark.asyncio
    async def test_session_failed_sends_message(self) -> None:
        bot = AsyncMock()
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message("session.failed", {"session_name": "broken", "error": "timeout"})
        await dispatcher._handle_message(msg)

        bot.send_message.assert_called_once()
        text = bot.send_message.call_args.kwargs["text"]
        assert "broken" in text
        assert "timeout" in text

    @pytest.mark.asyncio
    async def test_approval_required_sends_with_keyboard(self) -> None:
        bot = AsyncMock()
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message(
            "approval.required",
            {
                "session_name": "deploy",
                "action_description": "drop table",
                "action_id": "a-1",
            },
        )
        await dispatcher._handle_message(msg)

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args.kwargs
        assert "deploy" in call_kwargs["text"]
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio
    async def test_subagent_report_sends_message(self) -> None:
        bot = AsyncMock()
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message(
            "subagent.report_ready",
            {
                "parent_session": "orch-1",
                "subagent_name": "test-agent",
                "status": "completed",
            },
        )
        await dispatcher._handle_message(msg)

        bot.send_message.assert_called_once()
        text = bot.send_message.call_args.kwargs["text"]
        assert "test-agent" in text
        assert "completed" in text

    @pytest.mark.asyncio
    async def test_question_created_sends_message(self) -> None:
        bot = AsyncMock()
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message(
            "question.created",
            {
                "session_name": "plan",
                "question_text": "Which framework?",
                "question_id": "q-1",
            },
        )
        await dispatcher._handle_message(msg)

        bot.send_message.assert_called_once()
        text = bot.send_message.call_args.kwargs["text"]
        assert "Which framework?" in text
        assert "plan" in text

    @pytest.mark.asyncio
    async def test_ignores_events_not_in_filter(self) -> None:
        bot = AsyncMock()
        settings = _make_settings(telegram_notify_events=["session.completed"])
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message("session.failed", {"session_name": "x", "error": "y"})
        await dispatcher._handle_message(msg)

        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_send_when_chat_id_empty(self) -> None:
        bot = AsyncMock()
        settings = _make_settings(telegram_chat_id="")
        dispatcher = NotificationDispatcher(redis=AsyncMock(), bot=bot, settings=settings)

        msg = _make_pubsub_message("session.completed", {"session_name": "x", "summary": "y"})
        await dispatcher._handle_message(msg)

        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_disconnect_logs_and_continues(self) -> None:
        """Dispatcher logs error when Redis drops -- no unhandled exception."""
        bot = AsyncMock()
        redis_mock = AsyncMock()
        pubsub_mock = AsyncMock()
        pubsub_mock.psubscribe = AsyncMock(side_effect=ConnectionError("Redis gone"))
        redis_mock.pubsub.return_value = pubsub_mock
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=redis_mock, bot=bot, settings=settings)

        # _listen should catch the error and return gracefully
        with patch("codehive.clients.telegram.notifications.logger") as mock_logger:
            await dispatcher._listen()
            mock_logger.exception.assert_called_once()


class TestDispatcherLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        bot = AsyncMock()
        redis_mock = AsyncMock()
        settings = _make_settings()
        dispatcher = NotificationDispatcher(redis=redis_mock, bot=bot, settings=settings)

        # Patch _listen to be a no-op coroutine that waits for cancellation
        async def _fake_listen() -> None:
            await asyncio.sleep(999)

        with patch.object(dispatcher, "_listen", side_effect=_fake_listen):
            await dispatcher.start()
            assert dispatcher._task is not None
            await dispatcher.stop()
            assert dispatcher._task is None


# ---------------------------------------------------------------------------
# Callback query handler tests
# ---------------------------------------------------------------------------


class TestCallbackQueryHandler:
    @pytest.mark.asyncio
    async def test_approve_calls_api_and_edits(self) -> None:
        mock_resp = _mock_response(200, {"status": "approved"})
        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update_with_callback("approve:act-99")
        context = _make_context(http_client=http_client)
        await callback_query_handler(update, context)

        http_client.post.assert_called_once_with("/api/sessions/act-99/approve")
        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Approved" in edit_text

    @pytest.mark.asyncio
    async def test_reject_calls_api_and_edits(self) -> None:
        mock_resp = _mock_response(200, {"status": "rejected"})
        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update_with_callback("reject:act-55")
        context = _make_context(http_client=http_client)
        await callback_query_handler(update, context)

        http_client.post.assert_called_once_with("/api/sessions/act-55/reject")
        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Rejected" in edit_text

    @pytest.mark.asyncio
    async def test_api_error_edits_message_with_error(self) -> None:
        mock_resp = _mock_response(500, {"detail": "Internal server error"})
        http_client = AsyncMock(spec=httpx.AsyncClient)
        http_client.post = AsyncMock(return_value=mock_resp)

        update = _make_update_with_callback("approve:act-1")
        context = _make_context(http_client=http_client)
        await callback_query_handler(update, context)

        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Error" in edit_text

    @pytest.mark.asyncio
    async def test_unknown_format_replies_error(self) -> None:
        update = _make_update_with_callback("garbage")
        context = _make_context()
        await callback_query_handler(update, context)

        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Error" in edit_text


# ---------------------------------------------------------------------------
# Config integration tests
# ---------------------------------------------------------------------------


class TestConfigIntegration:
    def test_chat_id_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEHIVE_TELEGRAM_CHAT_ID", "99999")
        monkeypatch.setenv("CODEHIVE_TELEGRAM_BOT_TOKEN", "t")
        s = Settings()
        assert s.telegram_chat_id == "99999"

    def test_notify_events_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CODEHIVE_TELEGRAM_NOTIFY_EVENTS",
            '["session.completed","session.failed"]',
        )
        monkeypatch.setenv("CODEHIVE_TELEGRAM_BOT_TOKEN", "t")
        s = Settings()
        assert s.telegram_notify_events == ["session.completed", "session.failed"]

    def test_default_notify_events_includes_all_five(self) -> None:
        s = Settings()
        expected = {
            "approval.required",
            "session.completed",
            "session.failed",
            "subagent.report_ready",
            "question.created",
        }
        assert set(s.telegram_notify_events) == expected
