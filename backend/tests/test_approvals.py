"""Tests for approval gates: policy engine, engine interception, and API endpoints."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from codehive.api.app import create_app
from codehive.api.routes.approvals import (
    add_request,
    clear_stores,
)
from codehive.core.approval import (
    ApprovalRequest,
    ApprovalRule,
    check_action,
    create_approval_request,
    get_default_policy,
    resolve_request,
)
from codehive.engine.native import NativeEngine
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner


# ---------------------------------------------------------------------------
# Helpers
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


def _make_engine(tmp_path: Path) -> tuple[NativeEngine, dict[str, Any]]:
    """Create a NativeEngine with mocked dependencies."""
    client = AsyncMock()
    event_bus = AsyncMock()
    file_ops = FileOps(tmp_path)
    shell_runner = ShellRunner()
    git_ops = GitOps(tmp_path)
    diff_service = DiffService()

    engine = NativeEngine(
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


async def _collect_events(aiter: Any) -> list[dict]:
    """Collect all events from an async iterator."""
    events = []
    async for event in aiter:
        events.append(event)
    return events


# ===========================================================================
# Unit: Approval Policy Rules
# ===========================================================================


class TestDefaultPolicy:
    def test_default_policy_enabled(self):
        """get_default_policy() returns a policy with enabled=True."""
        policy = get_default_policy()
        assert policy.enabled is True

    def test_default_policy_has_at_least_5_rules(self):
        """get_default_policy() returns at least 5 rules."""
        policy = get_default_policy()
        assert len(policy.rules) >= 5

    def test_each_rule_has_required_fields(self):
        """Each default rule has non-empty id, description, and tool_name or pattern."""
        policy = get_default_policy()
        for rule in policy.rules:
            assert rule.id, "Rule must have an id"
            assert rule.description, "Rule must have a description"
            assert rule.tool_name is not None or rule.pattern is not None


class TestCheckAction:
    def test_file_delete_matches(self):
        """run_shell with 'rm -rf /tmp/data' matches file_delete rule."""
        policy = get_default_policy()
        rule = check_action(policy, "run_shell", {"command": "rm -rf /tmp/data"})
        assert rule is not None
        assert rule.id == "file_delete"

    def test_force_push_matches(self):
        """run_shell with 'git push --force origin main' matches force_push rule."""
        policy = get_default_policy()
        rule = check_action(policy, "run_shell", {"command": "git push --force origin main"})
        assert rule is not None
        assert rule.id == "force_push"

    def test_force_push_short_flag_matches(self):
        """run_shell with 'git push -f' matches force_push rule."""
        policy = get_default_policy()
        rule = check_action(policy, "run_shell", {"command": "git push -f origin main"})
        assert rule is not None
        assert rule.id == "force_push"

    def test_migration_apply_matches(self):
        """run_shell with 'python manage.py migrate' matches migration_apply rule."""
        policy = get_default_policy()
        rule = check_action(policy, "run_shell", {"command": "python manage.py migrate"})
        assert rule is not None
        assert rule.id == "migration_apply"

    def test_production_cmd_matches(self):
        """run_shell with 'kubectl apply -f production.yaml' matches production_cmd."""
        policy = get_default_policy()
        rule = check_action(policy, "run_shell", {"command": "kubectl apply -f production.yaml"})
        assert rule is not None
        assert rule.id == "production_cmd"

    def test_secret_edit_env_matches(self):
        """edit_file with path '.env.local' matches secret_edit rule."""
        policy = get_default_policy()
        rule = check_action(
            policy,
            "edit_file",
            {"path": ".env.local", "old_text": "a", "new_text": "b"},
        )
        assert rule is not None
        assert rule.id == "secret_edit"

    def test_secret_edit_credentials_matches(self):
        """edit_file with path 'credentials.json' matches secret_edit rule."""
        policy = get_default_policy()
        rule = check_action(
            policy,
            "edit_file",
            {"path": "credentials.json", "old_text": "a", "new_text": "b"},
        )
        assert rule is not None
        assert rule.id == "secret_edit"

    def test_read_file_returns_none(self):
        """read_file tool returns None (not a destructive tool)."""
        policy = get_default_policy()
        rule = check_action(policy, "read_file", {"path": "anything.txt"})
        assert rule is None

    def test_safe_shell_command_returns_none(self):
        """run_shell with 'ls -la' returns None (no matching rule)."""
        policy = get_default_policy()
        rule = check_action(policy, "run_shell", {"command": "ls -la"})
        assert rule is None

    def test_disabled_policy_returns_none(self):
        """check_action with disabled policy returns None."""
        policy = get_default_policy()
        policy.enabled = False
        rule = check_action(policy, "run_shell", {"command": "rm -rf /tmp"})
        assert rule is None

    def test_disabled_rule_not_matched(self):
        """check_action with disabled rule does not match."""
        policy = get_default_policy()
        for r in policy.rules:
            if r.id == "file_delete":
                r.enabled = False
        rule = check_action(policy, "run_shell", {"command": "rm -rf /tmp"})
        assert rule is None or rule.id != "file_delete"


# ===========================================================================
# Unit: ApprovalRequest lifecycle
# ===========================================================================


class TestApprovalRequestLifecycle:
    def test_create_request_pending(self):
        """create_approval_request returns a request with status 'pending'."""
        rule = ApprovalRule(id="test", description="Test rule", tool_name="run_shell")
        req = create_approval_request("session-1", "run_shell", {"command": "rm -rf /"}, rule)
        assert req.status == "pending"
        assert req.id  # UUID string
        assert req.session_id == "session-1"
        assert req.rule_id == "test"

    def test_resolve_approved(self):
        """resolve_request with approved=True sets status to 'approved'."""
        req = ApprovalRequest(
            id="req-1",
            session_id="s1",
            tool_name="run_shell",
            tool_input={},
            rule_id="test",
            description="test",
        )
        result = resolve_request(req, approved=True)
        assert result.status == "approved"

    def test_resolve_rejected(self):
        """resolve_request with approved=False sets status to 'rejected'."""
        req = ApprovalRequest(
            id="req-1",
            session_id="s1",
            tool_name="run_shell",
            tool_input={},
            rule_id="test",
            description="test",
        )
        result = resolve_request(req, approved=False)
        assert result.status == "rejected"


# ===========================================================================
# Integration: Engine gate interception
# ===========================================================================


class TestEngineGateInterception:
    @pytest.mark.asyncio
    async def test_destructive_tool_triggers_approval(self, tmp_path: Path):
        """run_shell with 'rm -rf /tmp' triggers approval gate."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        # Mock shell runner to track if it was called
        mocks["shell_runner"].run = AsyncMock()
        engine._shell_runner = mocks["shell_runner"]

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="run_shell",
                            input={"command": "rm -rf /tmp"},
                        )
                    ]
                )
            else:
                return MockResponse(content=[MockTextBlock(text="Waiting for approval.")])

        mocks["client"].messages.create = mock_create

        db_mock = MagicMock()
        events = await _collect_events(engine.send_message(session_id, "Delete files", db=db_mock))

        # Shell runner should NOT have been called
        mocks["shell_runner"].run.assert_not_called()

        # Should have emitted approval.required via event bus
        publish_calls = mocks["event_bus"].publish.call_args_list
        approval_events = [c for c in publish_calls if c.args[2] == "approval.required"]
        assert len(approval_events) >= 1
        event_data = approval_events[0].args[3]
        assert "action_id" in event_data
        assert event_data["tool_name"] == "run_shell"
        assert event_data["rule_id"] == "file_delete"

        # tool.call.finished result should indicate pending approval
        finished_events = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(finished_events) == 1
        assert finished_events[0]["result"].get("is_pending_approval") is True

    @pytest.mark.asyncio
    async def test_approve_executes_deferred_tool(self, tmp_path: Path):
        """After approval gate, approve_action executes the deferred tool."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        # Mock shell runner
        shell_mock = AsyncMock()
        shell_result = MagicMock()
        shell_result.stdout = "deleted"
        shell_result.stderr = ""
        shell_result.exit_code = 0
        shell_result.timed_out = False
        shell_mock.return_value = shell_result
        engine._shell_runner = MagicMock()
        engine._shell_runner.run = shell_mock

        # Trigger the approval gate directly
        result = await engine._execute_tool(
            "run_shell",
            {"command": "rm -rf /tmp/test"},
            session_id=session_id,
        )
        assert result.get("is_pending_approval") is True

        # Find the action_id
        state = engine._sessions[session_id]
        action_ids = list(state.pending_actions.keys())
        assert len(action_ids) == 1
        action_id = action_ids[0]

        # Shell should not have been called yet
        shell_mock.assert_not_called()

        # Approve the action
        approve_result = await engine.approve_action(session_id, action_id)
        assert approve_result is not None
        assert "is_error" not in approve_result

        # Shell should now have been called
        shell_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_returns_error(self, tmp_path: Path):
        """After approval gate, reject_action returns error without executing."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        # Mock shell runner
        shell_mock = AsyncMock()
        engine._shell_runner = MagicMock()
        engine._shell_runner.run = shell_mock

        # Trigger the approval gate
        result = await engine._execute_tool(
            "run_shell",
            {"command": "rm -rf /tmp/test"},
            session_id=session_id,
        )
        assert result.get("is_pending_approval") is True

        state = engine._sessions[session_id]
        action_id = list(state.pending_actions.keys())[0]

        # Reject the action
        reject_result = await engine.reject_action(session_id, action_id, reason="Too dangerous")
        assert reject_result is not None
        assert reject_result.get("is_error") is True
        assert "rejected" in reject_result["content"].lower()

        # Shell should NOT have been called
        shell_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_safe_command_no_gate(self, tmp_path: Path):
        """run_shell with 'ls -la' (safe) does not trigger approval gate."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        result = await engine._execute_tool(
            "run_shell",
            {"command": "ls -la"},
            session_id=session_id,
        )
        # Should execute directly, not pending approval
        assert result.get("is_pending_approval") is not True
        parsed = json.loads(result["content"])
        assert parsed["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_edit_env_triggers_gate(self, tmp_path: Path):
        """edit_file for '.env' triggers the secret_edit approval gate."""
        (tmp_path / ".env").write_text("SECRET=old_value")
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        result = await engine._execute_tool(
            "edit_file",
            {"path": ".env", "old_text": "old_value", "new_text": "new_value"},
            session_id=session_id,
        )
        assert result.get("is_pending_approval") is True
        assert "secret" in result["content"].lower() or "approval" in result["content"].lower()


# ===========================================================================
# Integration: API endpoints
# ===========================================================================


class TestApprovalsAPI:
    def setup_method(self):
        clear_stores()
        self.app = create_app()
        from codehive.api.deps import get_current_user

        self.app.dependency_overrides[get_current_user] = lambda: None
        self.client = TestClient(self.app)

    def test_list_approvals_empty(self):
        """GET /api/sessions/{id}/approvals returns empty list with no pending."""
        sid = str(uuid.uuid4())
        resp = self.client.get(f"/api/sessions/{sid}/approvals")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_approvals_with_pending(self):
        """After adding a request, GET returns it."""
        sid = str(uuid.uuid4())
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            session_id=sid,
            tool_name="run_shell",
            tool_input={"command": "rm -rf /"},
            rule_id="file_delete",
            description="File deletion via shell",
            status="pending",
        )
        add_request(req)
        resp = self.client.get(f"/api/sessions/{sid}/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == req.id
        assert data[0]["status"] == "pending"

    def test_approve_valid_action(self):
        """POST /approve with valid action_id returns 200."""
        sid = str(uuid.uuid4())
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            session_id=sid,
            tool_name="run_shell",
            tool_input={"command": "rm -rf /"},
            rule_id="file_delete",
            description="File deletion",
            status="pending",
        )
        add_request(req)
        resp = self.client.post(f"/api/sessions/{sid}/approve", json={"action_id": req.id})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_invalid_action(self):
        """POST /approve with invalid action_id returns 404."""
        sid = str(uuid.uuid4())
        resp = self.client.post(f"/api/sessions/{sid}/approve", json={"action_id": "nonexistent"})
        assert resp.status_code == 404

    def test_reject_valid_action(self):
        """POST /reject with valid action_id and reason returns 200."""
        sid = str(uuid.uuid4())
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            session_id=sid,
            tool_name="run_shell",
            tool_input={},
            rule_id="file_delete",
            description="File deletion",
            status="pending",
        )
        add_request(req)
        resp = self.client.post(
            f"/api/sessions/{sid}/reject",
            json={"action_id": req.id, "reason": "Too dangerous"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["reason"] == "Too dangerous"

    def test_reject_invalid_action(self):
        """POST /reject with invalid action_id returns 404."""
        sid = str(uuid.uuid4())
        resp = self.client.post(
            f"/api/sessions/{sid}/reject",
            json={"action_id": "nonexistent", "reason": "nope"},
        )
        assert resp.status_code == 404

    def test_get_default_approval_policy(self):
        """GET /approval-policy returns default policy."""
        sid = str(uuid.uuid4())
        resp = self.client.get(f"/api/sessions/{sid}/approval-policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert len(data["rules"]) >= 5

    def test_update_approval_policy(self):
        """PUT /approval-policy updates and persists."""
        sid = str(uuid.uuid4())
        new_policy = {
            "enabled": True,
            "rules": [
                {
                    "id": "custom_rule",
                    "description": "Custom rule",
                    "tool_name": "run_shell",
                    "pattern": "dangerous",
                    "enabled": True,
                }
            ],
        }
        resp = self.client.put(f"/api/sessions/{sid}/approval-policy", json=new_policy)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rules"]) == 1
        assert data["rules"][0]["id"] == "custom_rule"

        # Verify it persists on GET
        resp2 = self.client.get(f"/api/sessions/{sid}/approval-policy")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["rules"]) == 1
        assert data2["rules"][0]["id"] == "custom_rule"

    def test_update_policy_disable_rule(self):
        """PUT /approval-policy can disable a specific rule."""
        sid = str(uuid.uuid4())
        # Get default policy
        resp = self.client.get(f"/api/sessions/{sid}/approval-policy")
        data = resp.json()
        # Disable the first rule
        data["rules"][0]["enabled"] = False
        resp2 = self.client.put(f"/api/sessions/{sid}/approval-policy", json=data)
        assert resp2.status_code == 200
        assert resp2.json()["rules"][0]["enabled"] is False
        # Verify on GET
        resp3 = self.client.get(f"/api/sessions/{sid}/approval-policy")
        assert resp3.json()["rules"][0]["enabled"] is False
