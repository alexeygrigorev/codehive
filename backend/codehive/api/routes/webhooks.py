"""Webhook endpoint for receiving GitHub webhook deliveries."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.db.models import Project
from codehive.integrations.github.triggers import TriggerResult, handle_issue_event
from codehive.integrations.github.webhook import (
    SUPPORTED_ISSUE_ACTIONS,
    parse_webhook_event,
    verify_signature,
)

logger = logging.getLogger(__name__)

webhooks_router = APIRouter(tags=["webhooks"])


@webhooks_router.post("/api/webhooks/github")
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive a GitHub webhook delivery.

    - Reads raw body for signature verification.
    - Looks up project by matching repository owner/name.
    - Validates X-Hub-Signature-256 if webhook_secret is configured.
    - Routes to handler based on event type and action.
    """
    raw_body = await request.body()
    body = await request.json()
    headers = dict(request.headers)

    # Parse event
    event = parse_webhook_event(headers, body)

    # Extract repository info from payload
    repository = body.get("repository", {})
    repo_owner = repository.get("owner", {}).get("login", "")
    repo_name = repository.get("name", "")

    # Look up matching project
    project = await _find_project_by_repo(db, repo_owner, repo_name)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail="No project configured for this repository",
        )

    # Verify signature if webhook_secret is configured
    config = project.github_config or {}
    webhook_secret = config.get("webhook_secret")
    signature_header = headers.get("x-hub-signature-256", "")

    if webhook_secret:
        if not verify_signature(raw_body, signature_header, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning(
            "No webhook_secret configured for project %s; skipping signature verification",
            project.id,
        )

    # Route by event type
    if event.event_type != "issues":
        return _result_dict(TriggerResult(issue_id=None, session_id=None, action_taken="ignored"))

    if event.action not in SUPPORTED_ISSUE_ACTIONS:
        return _result_dict(TriggerResult(issue_id=None, session_id=None, action_taken="ignored"))

    # Handle the issue event
    trigger_mode = config.get("trigger_mode", "manual")
    result = await handle_issue_event(db, project.id, event, trigger_mode)

    return _result_dict(result)


async def _find_project_by_repo(db: AsyncSession, owner: str, repo: str) -> Project | None:
    """Find a project whose github_config matches the given owner and repo."""
    # Query all projects that have github_config set
    stmt = select(Project).where(Project.github_config.isnot(None))
    projects = (await db.execute(stmt)).scalars().all()

    for project in projects:
        config = project.github_config or {}
        if config.get("owner") == owner and config.get("repo") == repo:
            return project

    return None


def _result_dict(result: TriggerResult) -> dict:
    """Serialize a TriggerResult to a JSON-compatible dict."""
    return {
        "issue_id": str(result.issue_id) if result.issue_id else None,
        "session_id": str(result.session_id) if result.session_id else None,
        "action_taken": result.action_taken,
    }
