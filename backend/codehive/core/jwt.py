"""JWT access and refresh token creation and validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from codehive.config import Settings

_settings = Settings()

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when a token is invalid, expired, or has the wrong type."""


def create_access_token(
    user_id: uuid.UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for *user_id*."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=_settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": now + expires_delta,
        "iat": now,
    }
    return jwt.encode(payload, _settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT refresh token for *user_id*."""
    if expires_delta is None:
        expires_delta = timedelta(days=_settings.refresh_token_expire_days)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": now + expires_delta,
        "iat": now,
    }
    return jwt.encode(payload, _settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Returns the payload dict.

    Raises :class:`TokenError` on invalid, expired, or malformed tokens.
    """
    try:
        payload = jwt.decode(token, _settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
    return payload
