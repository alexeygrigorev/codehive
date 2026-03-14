"""Async database session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.config import Settings


def create_async_engine_from_settings(
    database_url: str | None = None,
    **engine_kwargs,
):
    """Create an async SQLAlchemy engine.

    If *database_url* is not provided, reads from :class:`Settings`.
    """
    url = database_url or Settings().database_url
    return create_async_engine(url, **engine_kwargs)


def async_session_factory(
    database_url: str | None = None,
    **engine_kwargs,
) -> async_sessionmaker[AsyncSession]:
    """Return an ``async_sessionmaker`` bound to an async engine.

    If *database_url* is not provided, reads from :class:`Settings`.
    """
    engine = create_async_engine_from_settings(database_url, **engine_kwargs)
    return async_sessionmaker(engine, expire_on_commit=False)
