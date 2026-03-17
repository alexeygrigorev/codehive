"""FastAPI dependencies."""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.session import async_session_factory

_SessionFactory = async_session_factory()

_bearer_scheme = HTTPBearer(auto_error=False)

# A fixed UUID used as the anonymous user's ID when auth is disabled.
_ANON_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@dataclass
class AnonymousUser:
    """Sentinel user returned when auth is disabled."""

    id: uuid.UUID = field(default_factory=lambda: _ANON_USER_ID)
    email: str = "anonymous@codehive.local"
    username: str = "anonymous"
    is_active: bool = True
    is_admin: bool = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closing it when the request ends."""
    async with _SessionFactory() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Decode Bearer token and return the authenticated User.

    Returns 401 if the token is missing, invalid, expired, not an access
    token, or the user no longer exists / is inactive.

    When ``auth_enabled`` is ``False`` in settings, returns an
    ``AnonymousUser`` sentinel immediately (anonymous access).
    """
    from codehive.config import Settings

    if not Settings().auth_enabled:
        return AnonymousUser()

    from codehive.core.jwt import TokenError, decode_token
    from codehive.db.models import User

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_token(credentials.credentials)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not an access token",
        )

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user
