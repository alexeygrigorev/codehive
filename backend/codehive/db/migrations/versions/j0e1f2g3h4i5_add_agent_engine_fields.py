"""add agent_profiles table with preferred_engine and preferred_model columns

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-03-28 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j0e1f2g3h4i5"
down_revision: Union[str, Sequence[str], None] = "i9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_col():
    """Return a UUID-compatible column type for both dialects."""
    return sa.String(36)


def _table_exists(table_name: str) -> bool:
    """Check whether a table already exists (works for SQLite and PostgreSQL)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check whether a column already exists in a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Create agent_profiles table if needed, add preferred_engine/model columns."""
    if not _table_exists("agent_profiles"):
        op.create_table(
            "agent_profiles",
            sa.Column("id", _uuid_col(), nullable=False),
            sa.Column(
                "project_id",
                _uuid_col(),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.Unicode(255), nullable=False),
            sa.Column("role", sa.Unicode(50), nullable=False),
            sa.Column("avatar_seed", sa.Unicode(255), nullable=False),
            sa.Column("personality", sa.Text(), nullable=True),
            sa.Column("system_prompt_modifier", sa.Text(), nullable=True),
            sa.Column("preferred_engine", sa.Unicode(50), nullable=True),
            sa.Column("preferred_model", sa.Unicode(255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        # Table exists (e.g. created by metadata.create_all); just add new columns
        if not _column_exists("agent_profiles", "preferred_engine"):
            op.add_column(
                "agent_profiles",
                sa.Column("preferred_engine", sa.Unicode(50), nullable=True),
            )
        if not _column_exists("agent_profiles", "preferred_model"):
            op.add_column(
                "agent_profiles",
                sa.Column("preferred_model", sa.Unicode(255), nullable=True),
            )


def downgrade() -> None:
    """Remove preferred_engine and preferred_model columns from agent_profiles."""
    if _table_exists("agent_profiles"):
        if _column_exists("agent_profiles", "preferred_model"):
            op.drop_column("agent_profiles", "preferred_model")
        if _column_exists("agent_profiles", "preferred_engine"):
            op.drop_column("agent_profiles", "preferred_engine")
