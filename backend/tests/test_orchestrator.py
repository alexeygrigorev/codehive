"""Tests for orchestrator mode: tool filtering, system prompt, report aggregation, engine integration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codehive.engine.zai_engine import ZaiEngine, TOOL_DEFINITIONS
from codehive.engine.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    aggregate_reports,
    filter_tools,
)
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner


# ---------------------------------------------------------------------------
# Helpers: mock Anthropic response objects (same pattern as test_engine.py)
# ---------------------------------------------------------------------------


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "tool_1"
    name: str = "read_file"
    input: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.input is None:
            self.input = {}


@dataclass
class MockResponse:
    content: list = None  # type: ignore[assignment]
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = []


class _MockStream:
    """Mock for the Anthropic streaming context manager."""

    def __init__(self, response: MockResponse) -> None:
        self._response = response
        self._text_chunks: list[str] = []
        for block in response.content:
            if block.type == "text":
                self._text_chunks.append(block.text)

    async def __aenter__(self) -> _MockStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    @property
    def text_stream(self) -> _TextStreamIter:
        return _TextStreamIter(self._text_chunks)

    async def get_final_message(self) -> MockResponse:
        return self._response


class _TextStreamIter:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self._index = 0

    def __aiter__(self) -> _TextStreamIter:
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _make_engine(tmp_path: Path) -> tuple[ZaiEngine, dict[str, Any]]:
    """Create a ZaiEngine with mocked dependencies and return (engine, mocks)."""
    client = AsyncMock()
    event_bus = AsyncMock()
    file_ops = FileOps(tmp_path)
    shell_runner = ShellRunner()
    git_ops = GitOps(tmp_path)
    diff_service = DiffService()

    engine = ZaiEngine(
        client=client,
        event_bus=event_bus,
        file_ops=file_ops,
        shell_runner=shell_runner,
        git_ops=git_ops,
        diff_service=diff_service,
    )

    return engine, {
        "client": client,
        "event_bus": event_bus,
        "file_ops": file_ops,
        "shell_runner": shell_runner,
        "git_ops": git_ops,
        "diff_service": diff_service,
    }


def _setup_stream_mock(mocks: dict[str, Any], responses: list[MockResponse] | MockResponse) -> None:
    if isinstance(responses, MockResponse):
        responses = [responses]
    call_count = 0

    def stream_side_effect(**kwargs: Any) -> _MockStream:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return _MockStream(responses[idx])

    mocks["client"].messages.stream = MagicMock(side_effect=stream_side_effect)


async def _collect_events(aiter: Any) -> list[dict]:
    """Collect all events from an async iterator."""
    events = []
    async for event in aiter:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Unit: Orchestrator tool filtering
# ---------------------------------------------------------------------------


class TestOrchestratorToolFiltering:
    def test_filter_returns_exactly_six_tools(self):
        """filter_tools(TOOL_DEFINITIONS) returns exactly 6 allowed tools."""
        filtered = filter_tools(TOOL_DEFINITIONS)
        names = {t["name"] for t in filtered}
        assert names == {
            "spawn_subagent",
            "read_file",
            "search_files",
            "run_shell",
            "get_subsession_result",
            "list_subsessions",
        }
        assert len(filtered) == 6

    def test_edit_file_not_in_filtered(self):
        """edit_file is NOT in the filtered list."""
        filtered = filter_tools(TOOL_DEFINITIONS)
        names = [t["name"] for t in filtered]
        assert "edit_file" not in names

    def test_git_commit_not_in_filtered(self):
        """git_commit is NOT in the filtered list."""
        filtered = filter_tools(TOOL_DEFINITIONS)
        names = [t["name"] for t in filtered]
        assert "git_commit" not in names

    def test_filter_empty_list(self):
        """filter_tools with an empty list returns an empty list."""
        assert filter_tools([]) == []


# ---------------------------------------------------------------------------
# Unit: Orchestrator system prompt
# ---------------------------------------------------------------------------


class TestOrchestratorSystemPrompt:
    def test_prompt_is_non_empty_string(self):
        """ORCHESTRATOR_SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(ORCHESTRATOR_SYSTEM_PROMPT, str)
        assert len(ORCHESTRATOR_SYSTEM_PROMPT) > 0

    def test_prompt_contains_key_phrases(self):
        """Prompt contains key phrases about planning and delegation."""
        lower = ORCHESTRATOR_SYSTEM_PROMPT.lower()
        assert "plan" in lower
        assert "sub-agent" in lower or "subagent" in lower
        assert "do not edit files" in lower or "not edit files" in lower


# ---------------------------------------------------------------------------
# Unit: aggregate_reports
# ---------------------------------------------------------------------------


class TestAggregateReports:
    def test_empty_reports(self):
        """Empty list returns zeroed counts with overall_status='all_completed'."""
        result = aggregate_reports([])
        assert result == {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "blocked": 0,
            "files_changed": [],
            "warnings": [],
            "overall_status": "all_completed",
        }

    def test_all_completed(self):
        """3 completed reports: merged files, overall_status='all_completed'."""
        reports = [
            {"status": "completed", "files_changed": ["a.py", "b.py"], "warnings": []},
            {"status": "completed", "files_changed": ["c.py"], "warnings": []},
            {"status": "completed", "files_changed": ["d.py"], "warnings": []},
        ]
        result = aggregate_reports(reports)
        assert result["total"] == 3
        assert result["completed"] == 3
        assert result["failed"] == 0
        assert result["blocked"] == 0
        assert set(result["files_changed"]) == {"a.py", "b.py", "c.py", "d.py"}
        assert result["overall_status"] == "all_completed"

    def test_one_completed_one_failed(self):
        """Mixed completed/failed: overall_status='has_failures'."""
        reports = [
            {"status": "completed", "files_changed": ["a.py"], "warnings": []},
            {"status": "failed", "files_changed": [], "warnings": ["build failed"]},
        ]
        result = aggregate_reports(reports)
        assert result["total"] == 2
        assert result["completed"] == 1
        assert result["failed"] == 1
        assert result["overall_status"] == "has_failures"

    def test_one_completed_one_blocked(self):
        """Mixed completed/blocked: overall_status='has_blocked'."""
        reports = [
            {"status": "completed", "files_changed": ["a.py"], "warnings": []},
            {"status": "blocked", "files_changed": [], "warnings": []},
        ]
        result = aggregate_reports(reports)
        assert result["total"] == 2
        assert result["completed"] == 1
        assert result["blocked"] == 1
        assert result["overall_status"] == "has_blocked"

    def test_failures_take_priority_over_blocked(self):
        """When both failed and blocked exist, overall_status='has_failures'."""
        reports = [
            {"status": "completed", "files_changed": [], "warnings": []},
            {"status": "failed", "files_changed": [], "warnings": []},
            {"status": "blocked", "files_changed": [], "warnings": []},
        ]
        result = aggregate_reports(reports)
        assert result["overall_status"] == "has_failures"

    def test_files_changed_deduplicated(self):
        """Overlapping files_changed are deduplicated."""
        reports = [
            {"status": "completed", "files_changed": ["a.py", "b.py"], "warnings": []},
            {"status": "completed", "files_changed": ["b.py", "c.py"], "warnings": []},
        ]
        result = aggregate_reports(reports)
        assert len(result["files_changed"]) == 3
        assert set(result["files_changed"]) == {"a.py", "b.py", "c.py"}

    def test_warnings_merged_not_deduplicated(self):
        """Warnings are merged (concatenated), not deduplicated."""
        reports = [
            {"status": "completed", "files_changed": [], "warnings": ["warn1", "warn2"]},
            {"status": "completed", "files_changed": [], "warnings": ["warn2", "warn3"]},
        ]
        result = aggregate_reports(reports)
        assert result["warnings"] == ["warn1", "warn2", "warn2", "warn3"]


# ---------------------------------------------------------------------------
# Unit: ZaiEngine with orchestrator mode
# ---------------------------------------------------------------------------


class TestZaiEngineOrchestratorMode:
    @pytest.mark.asyncio
    async def test_orchestrator_mode_uses_filtered_tools_and_system_prompt(self, tmp_path: Path):
        """In orchestrator mode, API is called with filtered tools and system prompt."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="I will plan.")]))

        events = await _collect_events(
            engine.send_message(session_id, "Plan the work", mode="orchestrator")
        )

        # Verify API was called with filtered tools (6 tools) and system prompt
        call_kwargs = mocks["client"].messages.stream.call_args
        tools_passed = call_kwargs.kwargs["tools"]
        tool_names = {t["name"] for t in tools_passed}
        assert tool_names == {
            "spawn_subagent",
            "read_file",
            "search_files",
            "run_shell",
            "get_subsession_result",
            "list_subsessions",
        }
        assert len(tools_passed) == 6

        # System prompt included
        assert "system" in call_kwargs.kwargs
        assert call_kwargs.kwargs["system"] == ORCHESTRATOR_SYSTEM_PROMPT

        # Events still produced
        msg_events = [e for e in events if e["type"] == "message.created"]
        assert len(msg_events) == 2
        assert msg_events[1]["content"] == "I will plan."

    @pytest.mark.asyncio
    async def test_orchestrator_mode_tool_call_works(self, tmp_path: Path):
        """In orchestrator mode, allowed tool calls (spawn_subagent) execute normally."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        # Mock spawn_subagent manager
        mock_result = {
            "child_session_id": str(uuid.uuid4()),
            "parent_session_id": str(session_id),
            "mission": "implement feature",
            "role": "swe",
            "status": "idle",
        }
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.spawn_subagent = AsyncMock(return_value=mock_result)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="spawn_subagent",
                            input={
                                "mission": "implement feature",
                                "role": "swe",
                                "scope": ["src/main.py"],
                            },
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="Sub-agent spawned.")]),
            ],
        )

        db_mock = AsyncMock()
        events = await _collect_events(
            engine.send_message(session_id, "Spawn an agent", mode="orchestrator", db=db_mock)
        )

        # Verify tool.call.started and tool.call.finished events
        started = [e for e in events if e["type"] == "tool.call.started"]
        finished = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(started) == 1
        assert started[0]["tool_name"] == "spawn_subagent"
        assert len(finished) == 1
        assert not finished[0]["result"].get("is_error", False)

    @pytest.mark.asyncio
    async def test_default_mode_uses_full_tool_set(self, tmp_path: Path):
        """Without mode (or mode='execution'), full tool set and no system prompt."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Hello!")]))

        await _collect_events(engine.send_message(session_id, "Hi"))

        call_kwargs = mocks["client"].messages.stream.call_args
        tools_passed = call_kwargs.kwargs["tools"]
        tool_names = {t["name"] for t in tools_passed}
        # Full set: 10 tools (including query_agent, send_to_agent, get_subsession_result, list_subsessions)
        assert "edit_file" in tool_names
        assert "git_commit" in tool_names
        assert len(tools_passed) == 10

        # No system prompt
        assert "system" not in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# Unit: Defensive tool rejection in orchestrator mode
# ---------------------------------------------------------------------------


class TestDefensiveToolRejection:
    @pytest.mark.asyncio
    async def test_disallowed_tool_rejected_in_orchestrator_mode(self, tmp_path: Path):
        """edit_file tool call in orchestrator mode returns error, loop continues."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="edit_file",
                            input={
                                "path": "file.py",
                                "old_text": "old",
                                "new_text": "new",
                            },
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="Sorry, I cannot edit files.")]),
            ],
        )

        events = await _collect_events(
            engine.send_message(session_id, "Edit the file", mode="orchestrator")
        )

        # The tool call should have an error result
        finished = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(finished) == 1
        assert finished[0]["result"]["is_error"] is True
        assert "not available in orchestrator mode" in finished[0]["result"]["content"]

        # The loop continued and produced a final assistant message
        assistant_msgs = [
            e for e in events if e["type"] == "message.created" and e.get("role") == "assistant"
        ]
        assert len(assistant_msgs) == 1


# ---------------------------------------------------------------------------
# Unit: No regressions on default mode
# ---------------------------------------------------------------------------


class TestNoRegressions:
    @pytest.mark.asyncio
    async def test_default_mode_text_response_unchanged(self, tmp_path: Path):
        """send_message without mode behaves exactly as before."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Hello, I can help!")]))

        events = await _collect_events(engine.send_message(session_id, "Hi"))

        msg_events = [e for e in events if e["type"] == "message.created"]
        assert len(msg_events) == 2
        assert msg_events[0]["role"] == "user"
        assert msg_events[1]["role"] == "assistant"
        assert msg_events[1]["content"] == "Hello, I can help!"
