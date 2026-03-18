"""Async database session factory."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.config import Settings


def create_async_engine_from_settings(
    database_url: str | None = None,
    **engine_kwargs,
):
    """Create an async SQLAlchemy engine.

    If *database_url* is not provided, reads from :class:`Settings`.

    For SQLite URLs the engine is configured with:
    - ``connect_args={"check_same_thread": False}``
    - WAL journal mode enabled via a connection event listener
    """
    url = database_url or Settings().database_url
    if url.startswith("sqlite"):
        engine_kwargs.setdefault("connect_args", {"check_same_thread": False})
    engine = create_async_engine(url, **engine_kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def async_session_factory(
    database_url: str | None = None,
    **engine_kwargs,
) -> async_sessionmaker[AsyncSession]:
    """Return an ``async_sessionmaker`` bound to an async engine.

    If *database_url* is not provided, reads from :class:`Settings`.
    """
    engine = create_async_engine_from_settings(database_url, **engine_kwargs)
    return async_sessionmaker(engine, expire_on_commit=False)
