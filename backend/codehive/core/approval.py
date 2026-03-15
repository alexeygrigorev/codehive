"""Approval policy engine: define rules, check actions, manage approval requests."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ApprovalRule:
    """A single rule that triggers an approval gate."""

    id: str  # e.g. "file_delete", "force_push"
    description: str  # Human-readable description
    tool_name: str | None = None  # Match specific tool (e.g. "run_shell")
    pattern: str | None = None  # Regex pattern to match against tool input
    enabled: bool = True


@dataclass
class ApprovalPolicy:
    """A set of rules governing which actions require approval."""

    rules: list[ApprovalRule] = field(default_factory=list)
    enabled: bool = True  # Global kill switch


@dataclass
class ApprovalRequest:
    """A pending approval request."""

    id: str  # UUID string
    session_id: str
    tool_name: str
    tool_input: dict
    rule_id: str  # Which rule triggered this
    description: str  # Human-readable description of the action
    status: str = "pending"  # "pending" | "approved" | "rejected"
    created_at: str = ""  # ISO timestamp

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


def get_default_policy() -> ApprovalPolicy:
    """Return the default set of approval rules."""
    return ApprovalPolicy(
        rules=[
            ApprovalRule(
                id="file_delete",
                description="File deletion via shell",
                tool_name="run_shell",
                pattern=r"rm\s",
            ),
            ApprovalRule(
                id="force_push",
                description="Force push to remote",
                tool_name="run_shell",
                pattern=r"git\s+push\s+.*--force|git\s+push\s+-f",
            ),
            ApprovalRule(
                id="migration_apply",
                description="Database migration apply",
                tool_name="run_shell",
                pattern=r"migrate\b|migration",
            ),
            ApprovalRule(
                id="production_cmd",
                description="Production/deployment commands",
                tool_name="run_shell",
                pattern=r"deploy\b|production\b|prod\b",
            ),
            ApprovalRule(
                id="secret_edit",
                description="Secret-related file edits",
                tool_name="edit_file",
                pattern=r"\.env\b|secret|credential|\.pem|\.key",
            ),
        ],
        enabled=True,
    )


def _get_searchable_text(tool_name: str, tool_input: dict) -> str:
    """Extract the text to match against from tool input."""
    if tool_name == "run_shell":
        return tool_input.get("command", "")
    elif tool_name == "edit_file":
        return tool_input.get("path", "")
    return ""


def check_action(
    policy: ApprovalPolicy,
    tool_name: str,
    tool_input: dict,
) -> ApprovalRule | None:
    """Check whether a tool call requires approval.

    Returns the matching rule if approval is required, None otherwise.
    """
    if not policy.enabled:
        return None

    searchable = _get_searchable_text(tool_name, tool_input)

    for rule in policy.rules:
        if not rule.enabled:
            continue
        # Match tool_name if specified
        if rule.tool_name is not None and rule.tool_name != tool_name:
            continue
        # Match pattern against searchable text
        if rule.pattern is not None:
            if not re.search(rule.pattern, searchable):
                continue
        # All conditions matched
        return rule

    return None


def create_approval_request(
    session_id: str,
    tool_name: str,
    tool_input: dict,
    rule: ApprovalRule,
) -> ApprovalRequest:
    """Create a pending approval request."""
    return ApprovalRequest(
        id=str(uuid.uuid4()),
        session_id=session_id,
        tool_name=tool_name,
        tool_input=tool_input,
        rule_id=rule.id,
        description=rule.description,
        status="pending",
    )


def resolve_request(request: ApprovalRequest, *, approved: bool) -> ApprovalRequest:
    """Mark an approval request as approved or rejected."""
    request.status = "approved" if approved else "rejected"
    return request
