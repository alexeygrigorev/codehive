"""add remote_targets table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-15 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create remote_targets table."""
    op.create_table(
        "remote_targets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("label", sa.Unicode(255), nullable=False),
        sa.Column("host", sa.Unicode(500), nullable=False),
        sa.Column("port", sa.Integer(), server_default=sa.text("22"), nullable=False),
        sa.Column("username", sa.Unicode(255), nullable=False),
        sa.Column("key_path", sa.Unicode(1024), nullable=True),
        sa.Column(
            "known_hosts_policy",
            sa.Unicode(50),
            server_default="auto",
            nullable=False,
        ),
        sa.Column("last_connected_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Unicode(50),
            server_default="disconnected",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop remote_targets table."""
    op.drop_table("remote_targets")
