"""Webhook receiver: validate HMAC-SHA256 signature, parse payload, route by event type."""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Supported event types and actions
SUPPORTED_ISSUE_ACTIONS = {"opened", "edited", "closed", "reopened"}


@dataclass
class WebhookEvent:
    """Parsed webhook event."""

    event_type: str
    action: str
    payload: dict


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify the X-Hub-Signature-256 header using HMAC-SHA256.

    Uses hmac.compare_digest for constant-time comparison to prevent timing attacks.
    """
    if not signature_header:
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    expected_sig = signature_header[len(prefix) :]
    mac = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256)
    computed_sig = mac.hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


def parse_webhook_event(headers: dict, body: dict) -> WebhookEvent:
    """Extract event type from X-GitHub-Event header and action from body.

    Returns a WebhookEvent with event_type, action, and the full payload.
    """
    event_type = headers.get("x-github-event", "")
    action = body.get("action", "")

    return WebhookEvent(
        event_type=event_type,
        action=action,
        payload=body,
    )
