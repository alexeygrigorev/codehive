"""Firebase Cloud Messaging integration: send push notifications via firebase-admin SDK."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_firebase_app = None
_initialized = False


def _ensure_initialized() -> bool:
    """Initialize Firebase Admin SDK from FIREBASE_CREDENTIALS_JSON env var.

    Returns True if Firebase is available, False otherwise.
    """
    global _firebase_app, _initialized

    if _initialized:
        return _firebase_app is not None

    _initialized = True

    creds_path = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
    if not creds_path:
        logger.debug("FIREBASE_CREDENTIALS_JSON not set; FCM sending disabled")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(creds_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
        return True
    except Exception:
        logger.exception("Failed to initialize Firebase Admin SDK")
        return False


def send_fcm_push(token: str, title: str, body: str, data: dict | None = None) -> bool:
    """Send a push notification via FCM.

    Returns True if the message was sent successfully, False otherwise.
    Raises ``UnregisteredError`` if the token is invalid/unregistered.
    """
    if not _ensure_initialized():
        logger.debug("Firebase not initialized; skipping FCM push")
        return False

    from firebase_admin import messaging
    from firebase_admin.exceptions import InvalidArgumentError, NotFoundError

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        token=token,
    )

    try:
        messaging.send(message)
        return True
    except (messaging.UnregisteredError, InvalidArgumentError, NotFoundError):
        raise
    except Exception:
        logger.exception("FCM send failed for token %s", token[:20])
        return False


class UnregisteredError(Exception):
    """Raised when an FCM token is no longer valid."""
