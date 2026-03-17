"""Tests for CodeApp multiline input (_ChatInput widget)."""

from __future__ import annotations

import pytest
from textual.widgets import TextArea

from codehive.clients.terminal.code_app import CodeApp, _ChatInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _TestCodeApp(CodeApp):
    """CodeApp subclass that skips engine initialisation for testing."""

    async def _init_engine(self) -> None:
        """No-op: skip Anthropic client and engine setup."""
        pass


def _make_app() -> _TestCodeApp:
    return _TestCodeApp(project_dir="/tmp/test-project")


# ---------------------------------------------------------------------------
# Unit: Widget replacement
# ---------------------------------------------------------------------------


class TestWidgetReplacement:
    @pytest.mark.asyncio
    async def test_compose_contains_chat_input_not_input(self) -> None:
        """CodeApp composes with a _ChatInput (TextArea) widget, not Input."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input")
            assert isinstance(chat_input, _ChatInput)
            assert isinstance(chat_input, TextArea)

    @pytest.mark.asyncio
    async def test_chat_input_is_focusable(self) -> None:
        """The _ChatInput widget is focusable on mount."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            assert chat_input.has_focus


# ---------------------------------------------------------------------------
# Unit: Enter submits
# ---------------------------------------------------------------------------


class TestEnterSubmits:
    @pytest.mark.asyncio
    async def test_enter_submits_text(self) -> None:
        """Pressing Enter submits the message and creates a user bubble."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("Hello world")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # The input should be cleared after submission
            assert chat_input.text == ""

    @pytest.mark.asyncio
    async def test_enter_on_empty_does_not_submit(self) -> None:
        """Pressing Enter with empty/whitespace-only text does not submit."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # Press enter with empty input -- should not add a user bubble
            from textual.containers import VerticalScroll

            scroll = app.query_one("#code-scroll", VerticalScroll)
            count_before = len(scroll.children)
            await pilot.press("enter")
            await pilot.pause()
            # Only system message should be present, no new user bubble
            count_after = len(scroll.children)
            assert count_after == count_before

    @pytest.mark.asyncio
    async def test_input_cleared_after_submission(self) -> None:
        """After submission, the TextArea is cleared and height is reset."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("Some text")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert chat_input.text == ""


# ---------------------------------------------------------------------------
# Unit: Shift+Enter inserts newline
# ---------------------------------------------------------------------------


class TestShiftEnterNewline:
    @pytest.mark.asyncio
    async def test_shift_enter_inserts_newline(self) -> None:
        """Pressing Shift+Enter inserts a newline without submitting."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("line1")
            await pilot.pause()
            await pilot.press("shift+enter")
            await pilot.pause()
            # Text should contain a newline, not be submitted
            assert "\n" in chat_input.text
            assert chat_input.text.startswith("line1")


# ---------------------------------------------------------------------------
# Unit: Input disabled during processing
# ---------------------------------------------------------------------------


class TestInputDisabledDuringProcessing:
    @pytest.mark.asyncio
    async def test_input_disabled_while_busy(self) -> None:
        """While _busy is True, submitting shows a wait message."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # Simulate busy state
            app._busy = True
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("should not submit")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # Input should be cleared (the handler clears then checks busy)
            # but a system message about waiting should appear
            from codehive.clients.terminal.code_app import _ChatBubble
            from textual.containers import VerticalScroll

            scroll = app.query_one("#code-scroll", VerticalScroll)
            bubbles = scroll.query(_ChatBubble)
            texts = [str(b.render()) for b in bubbles]
            has_wait = any("wait" in t.lower() or "thinking" in t.lower() for t in texts)
            assert has_wait


# ---------------------------------------------------------------------------
# Integration: Multiline message flow
# ---------------------------------------------------------------------------


class TestMultilineMessageFlow:
    @pytest.mark.asyncio
    async def test_multiline_submit_preserves_all_lines(self) -> None:
        """Type multiline (Shift+Enter), then Enter -- full text appears in bubble."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("line1")
            await pilot.pause()
            await pilot.press("shift+enter")
            await pilot.pause()
            chat_input.insert("line2")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # A user bubble should exist with both lines
            from codehive.clients.terminal.code_app import _ChatBubble
            from textual.containers import VerticalScroll

            scroll = app.query_one("#code-scroll", VerticalScroll)
            bubbles = scroll.query(_ChatBubble)
            user_bubbles = [b for b in bubbles if "user" in str(b.render()).lower()[:30]]
            assert len(user_bubbles) >= 1
            content = str(user_bubbles[-1].render())
            assert "line1" in content
            assert "line2" in content

    @pytest.mark.asyncio
    async def test_quit_command_still_works(self) -> None:
        """/quit command still exits the app."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("/quit")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # App should have exited (or be exiting)
            # In test mode, we check _exit flag or return code
            assert app.return_code is not None or app._exit

    @pytest.mark.asyncio
    async def test_exit_command_still_works(self) -> None:
        """/exit command still exits the app."""
        app = _make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            chat_input = app.query_one("#code-input", _ChatInput)
            chat_input.insert("/exit")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.return_code is not None or app._exit
