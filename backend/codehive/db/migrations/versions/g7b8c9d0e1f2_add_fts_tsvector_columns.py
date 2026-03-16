"""Add tsvector columns, GIN indexes, and triggers for full-text search.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-16 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Table -> (source columns for tsvector)
_TABLES = {
    "sessions": ["name"],
    "messages": ["content"],
    "issues": ["title", "description"],
    "events": ["type"],
}


def upgrade() -> None:
    """Add search_vector tsvector columns, GIN indexes, and update triggers."""
    for table, columns in _TABLES.items():
        # Add tsvector column
        op.execute(f"ALTER TABLE {table} ADD COLUMN search_vector tsvector")

        # Create GIN index
        op.execute(f"CREATE INDEX ix_{table}_search_vector ON {table} USING gin (search_vector)")

        # Build the tsvector expression from source columns
        coalesce_parts = " || ' ' || ".join(f"coalesce(NEW.{col}, '')" for col in columns)

        # Create trigger function
        op.execute(f"""
            CREATE FUNCTION {table}_search_vector_update() RETURNS trigger AS $$
            BEGIN
              NEW.search_vector := to_tsvector('english', {coalesce_parts});
              RETURN NEW;
            END
            $$ LANGUAGE plpgsql;
        """)

        # Create trigger
        op.execute(f"""
            CREATE TRIGGER {table}_search_vector_trigger
              BEFORE INSERT OR UPDATE ON {table}
              FOR EACH ROW EXECUTE FUNCTION {table}_search_vector_update();
        """)

        # Backfill existing rows
        concat_parts = " || ' ' || ".join(f"coalesce({col}, '')" for col in columns)
        op.execute(f"UPDATE {table} SET search_vector = to_tsvector('english', {concat_parts})")


def downgrade() -> None:
    """Drop triggers, trigger functions, indexes, and tsvector columns."""
    for table in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_search_vector_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {table}_search_vector_update()")
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_search_vector")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector")
