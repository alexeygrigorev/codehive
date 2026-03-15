"""Approval gate endpoints: list pending, approve, reject, manage policy."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codehive.core.approval import (
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalRule,
    get_default_policy,
    resolve_request,
)

# ---------------------------------------------------------------------------
# In-memory stores (per-session approval requests and policies)
# ---------------------------------------------------------------------------

# session_id (str) -> list of ApprovalRequest
_pending_requests: dict[str, list[ApprovalRequest]] = {}

# session_id (str) -> ApprovalPolicy
_session_policies: dict[str, ApprovalPolicy] = {}


def get_requests_for_session(session_id: str) -> list[ApprovalRequest]:
    """Return all approval requests for a session."""
    return _pending_requests.get(session_id, [])


def add_request(request: ApprovalRequest) -> None:
    """Register a new approval request."""
    sid = request.session_id
    if sid not in _pending_requests:
        _pending_requests[sid] = []
    _pending_requests[sid].append(request)


def find_request(session_id: str, action_id: str) -> ApprovalRequest | None:
    """Find a request by session and action ID."""
    for req in _pending_requests.get(session_id, []):
        if req.id == action_id:
            return req
    return None


def get_policy_for_session(session_id: str) -> ApprovalPolicy:
    """Return the approval policy for a session, creating default if needed."""
    if session_id not in _session_policies:
        _session_policies[session_id] = get_default_policy()
    return _session_policies[session_id]


def set_policy_for_session(session_id: str, policy: ApprovalPolicy) -> None:
    """Set the approval policy for a session."""
    _session_policies[session_id] = policy


def clear_stores() -> None:
    """Clear all in-memory stores (for testing)."""
    _pending_requests.clear()
    _session_policies.clear()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ApproveBody(BaseModel):
    action_id: str


class RejectBody(BaseModel):
    action_id: str
    reason: str = ""


class ApprovalRuleSchema(BaseModel):
    id: str
    description: str
    tool_name: str | None = None
    pattern: str | None = None
    enabled: bool = True


class ApprovalPolicySchema(BaseModel):
    rules: list[ApprovalRuleSchema] = Field(default_factory=list)
    enabled: bool = True


class ApprovalRequestRead(BaseModel):
    id: str
    session_id: str
    tool_name: str
    tool_input: dict
    rule_id: str
    description: str
    status: str
    created_at: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

approvals_router = APIRouter(prefix="/api/sessions", tags=["approvals"])


@approvals_router.get("/{session_id}/approvals", response_model=list[ApprovalRequestRead])
async def list_approvals(session_id: uuid.UUID) -> list[dict[str, Any]]:
    """List pending approval requests for a session."""
    sid = str(session_id)
    requests = get_requests_for_session(sid)
    pending = [r for r in requests if r.status == "pending"]
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "tool_name": r.tool_name,
            "tool_input": r.tool_input,
            "rule_id": r.rule_id,
            "description": r.description,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in pending
    ]


@approvals_router.post("/{session_id}/approve")
async def approve_action(session_id: uuid.UUID, body: ApproveBody) -> dict[str, str]:
    """Approve a pending action."""
    sid = str(session_id)
    request = find_request(sid, body.action_id)
    if request is None or request.status != "pending":
        raise HTTPException(status_code=404, detail="Pending action not found")
    resolve_request(request, approved=True)
    return {"status": "approved", "action_id": body.action_id}


@approvals_router.post("/{session_id}/reject")
async def reject_action(session_id: uuid.UUID, body: RejectBody) -> dict[str, str]:
    """Reject a pending action."""
    sid = str(session_id)
    request = find_request(sid, body.action_id)
    if request is None or request.status != "pending":
        raise HTTPException(status_code=404, detail="Pending action not found")
    resolve_request(request, approved=False)
    return {"status": "rejected", "action_id": body.action_id, "reason": body.reason}


@approvals_router.get("/{session_id}/approval-policy")
async def get_approval_policy(session_id: uuid.UUID) -> dict[str, Any]:
    """Get the current approval policy for a session."""
    sid = str(session_id)
    policy = get_policy_for_session(sid)
    return {
        "enabled": policy.enabled,
        "rules": [
            {
                "id": r.id,
                "description": r.description,
                "tool_name": r.tool_name,
                "pattern": r.pattern,
                "enabled": r.enabled,
            }
            for r in policy.rules
        ],
    }


@approvals_router.put("/{session_id}/approval-policy")
async def update_approval_policy(
    session_id: uuid.UUID, body: ApprovalPolicySchema
) -> dict[str, Any]:
    """Update the approval policy for a session."""
    sid = str(session_id)
    rules = [
        ApprovalRule(
            id=r.id,
            description=r.description,
            tool_name=r.tool_name,
            pattern=r.pattern,
            enabled=r.enabled,
        )
        for r in body.rules
    ]
    policy = ApprovalPolicy(rules=rules, enabled=body.enabled)
    set_policy_for_session(sid, policy)
    return {
        "enabled": policy.enabled,
        "rules": [
            {
                "id": r.id,
                "description": r.description,
                "tool_name": r.tool_name,
                "pattern": r.pattern,
                "enabled": r.enabled,
            }
            for r in policy.rules
        ],
    }
