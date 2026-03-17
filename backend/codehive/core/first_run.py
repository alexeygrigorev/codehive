"""First-run setup: detect empty DB, seed default workspace and admin user."""

import secrets
import string
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.auth import hash_password
from codehive.db.models import User, Workspace, WorkspaceMember


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

    Creates a default workspace ("Default") and an admin user. Credentials
    are read from environment variables:

    - ``CODEHIVE_ADMIN_USERNAME`` (default: ``"admin"``)
    - ``CODEHIVE_ADMIN_PASSWORD`` (if unset, a random password is generated)

    Returns a dict with ``username``, ``password``, and ``email`` on success,
    or ``None`` if seeding was skipped (users already exist).
    """
    from codehive.config import Settings

    settings = Settings()

    if not settings.auth_enabled:
        # When auth is disabled, only create the default workspace (no admin user).
        # Check if workspace already exists to be idempotent.
        ws_result = await session.execute(select(Workspace).where(Workspace.name == "Default"))
        if ws_result.scalar_one_or_none() is None:
            now = datetime.now(UTC).replace(tzinfo=None)
            workspace = Workspace(
                name="Default",
                root_path="/",
                settings={},
                created_at=now,
            )
            session.add(workspace)
            await session.commit()
        return None

    if not await is_first_run(session):
        return None

    username = settings.admin_username
    password = settings.admin_password or _generate_password()
    email = f"{username}@codehive.local"

    now = datetime.now(UTC).replace(tzinfo=None)

    # Create default workspace
    workspace = Workspace(
        name="Default",
        root_path="/",
        settings={},
        created_at=now,
    )
    session.add(workspace)
    await session.flush()

    # Create admin user
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_admin=True,
        is_active=True,
        workspace_id=workspace.id,
    )
    session.add(user)
    await session.flush()

    # Add admin as owner of the default workspace
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        created_at=now,
    )
    session.add(member)

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
