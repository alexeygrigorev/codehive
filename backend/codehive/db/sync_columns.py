"""Auto-sync missing SQLite columns on startup.

Compares SQLAlchemy model metadata against the physical SQLite schema
and issues ALTER TABLE ADD COLUMN for any columns that are missing.
This is purely additive -- no DROP, no recreate.
"""

import logging

from sqlalchemy import Connection, inspect, text

from codehive.db.models import Base

logger = logging.getLogger(__name__)


def sync_sqlite_columns(connection: Connection) -> None:
    """Inspect each table and ALTER TABLE ADD COLUMN for any missing columns.

    Must be called via ``await conn.run_sync(sync_sqlite_columns)`` inside
    an async engine transaction.  Only meaningful for SQLite -- other dialects
    use Alembic migrations.
    """
    inspector = inspect(connection)
    dialect = connection.dialect

    for table in Base.metadata.sorted_tables:
        # Get existing column names from the physical DB
        try:
            db_columns = inspector.get_columns(table.name)
        except Exception:
            # Table might not exist yet (will be created by create_all)
            continue

        existing_col_names = {col["name"] for col in db_columns}

        for column in table.columns:
            col_name = column.name
            if col_name in existing_col_names:
                continue

            # Build the ALTER TABLE ADD COLUMN statement
            col_type = column.type.compile(dialect=dialect)
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {col_name} {col_type}"

            if column.server_default is not None:
                default_text = column.server_default.arg
                # server_default.arg can be a text() clause or a plain string
                if hasattr(default_text, "text"):
                    default_text = default_text.text
                ddl += f" DEFAULT {default_text}"

            connection.execute(text(ddl))
            logger.info("Added column %s.%s (%s)", table.name, col_name, col_type)
