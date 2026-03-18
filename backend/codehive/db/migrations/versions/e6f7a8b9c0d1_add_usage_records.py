"""add usage_records table

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-03-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_col():
    """Return a UUID-compatible column type for both dialects."""
    return sa.String(36)


def upgrade() -> None:
    """Create usage_records table."""
    op.create_table(
        "usage_records",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("session_id", _uuid_col(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("model", sa.Unicode(255), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop usage_records table."""
    op.drop_table("usage_records")
