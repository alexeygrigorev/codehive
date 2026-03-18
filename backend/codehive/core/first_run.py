"""First-run setup: seed default admin user when auth is enabled."""

import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.auth import hash_password
from codehive.db.models import User


async def is_first_run(session: AsyncSession) -> bool:
    """Return True if the database has no users (first boot)."""
    result = await session.execute(select(func.count()).select_from(User))
    count = result.scalar_one()
    return count == 0


def _generate_password(length: int = 24) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def seed_first_run(session: AsyncSession) -> dict[str, str] | None:
    """Seed the database on first run.

    When auth is disabled, this is a no-op.
    When auth is enabled, creates an admin user on first run.

    Returns a dict with username, password, and email on success,
    or None if seeding was skipped.
    """
    from codehive.config import Settings

    settings = Settings()

    if not settings.auth_enabled:
        return None

    if not await is_first_run(session):
        return None

    username = settings.admin_username
    password = settings.admin_password or _generate_password()
    email = f"{username}@codehive.local"

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_admin=True,
        is_active=True,
    )
    session.add(user)
    await session.commit()

    return {"username": username, "password": password, "email": email}


def print_credentials(credentials: dict[str, str]) -> None:
    """Print first-run credentials to stdout."""
    print("=" * 60)
    print("CODEHIVE FIRST-RUN SETUP")
    print("=" * 60)
    print(f"  Admin username : {credentials['username']}")
    print(f"  Admin email    : {credentials['email']}")
    print(f"  Admin password : {credentials['password']}")
    print("=" * 60)
    print("Save these credentials -- the password will not be shown again.")
    print("=" * 60)
