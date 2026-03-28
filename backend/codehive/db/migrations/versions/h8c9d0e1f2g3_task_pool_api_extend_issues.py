"""task pool API: extend issues with new fields and add issue_log_entries table

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-03-28 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, Sequence[str], None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_col():
    """Return a UUID-compatible column type for both dialects."""
    return sa.String(36)


def upgrade() -> None:
    """Add new columns to issues and create issue_log_entries table."""
    # Add new columns to issues table
    op.add_column("issues", sa.Column("acceptance_criteria", sa.Text(), nullable=True))
    op.add_column("issues", sa.Column("assigned_agent", sa.Unicode(50), nullable=True))
    op.add_column(
        "issues",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "issues",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create issue_log_entries table
    op.create_table(
        "issue_log_entries",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("issue_id", _uuid_col(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("agent_role", sa.Unicode(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove issue_log_entries table and new columns from issues."""
    op.drop_table("issue_log_entries")
    op.drop_column("issues", "updated_at")
    op.drop_column("issues", "priority")
    op.drop_column("issues", "assigned_agent")
    op.drop_column("issues", "acceptance_criteria")
