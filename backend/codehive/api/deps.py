"""FastAPI dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.session import async_session_factory

_SessionFactory = async_session_factory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closing it when the request ends."""
    async with _SessionFactory() as session:
        yield session
