"""add github_config to projects

Revision ID: a1b2c3d4e5f6
Revises: 5ee984c421f1
Create Date: 2026-03-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5ee984c421f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add github_config JSON column to projects table."""
    op.add_column(
        "projects",
        sa.Column(
            "github_config",
            sa.JSON().with_variant(PG_JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove github_config column from projects table."""
    op.drop_column("projects", "github_config")
