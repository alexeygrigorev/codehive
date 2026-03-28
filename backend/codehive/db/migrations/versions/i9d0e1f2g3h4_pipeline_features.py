"""pipeline features: sessions role/task_id/pipeline_step, tasks pipeline_status,
task_pipeline_logs, custom_roles, custom_archetypes tables

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3, e6f7a8b9c0d1
Create Date: 2026-03-28 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9d0e1f2g3h4"
down_revision: Union[str, Sequence[str], None] = ("h8c9d0e1f2g3", "e6f7a8b9c0d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_col():
    """Return a UUID-compatible column type for both dialects."""
    return sa.String(36)


def _json_col():
    """Return a JSON column type portable across PostgreSQL and SQLite."""
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    return sa.JSON().with_variant(PG_JSONB(), "postgresql")


def upgrade() -> None:
    """Add pipeline-related columns and tables."""
    # --- New columns on sessions ---
    op.add_column("sessions", sa.Column("role", sa.Unicode(50), nullable=True))
    op.add_column("sessions", sa.Column("task_id", _uuid_col(), nullable=True))
    op.add_column("sessions", sa.Column("pipeline_step", sa.Unicode(50), nullable=True))

    # Add FK constraint separately due to circular reference (sessions <-> tasks).
    # Use batch mode so SQLite can handle the ALTER via copy-and-move.
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.create_foreign_key(
            "fk_sessions_task_id",
            "tasks",
            ["task_id"],
            ["id"],
        )

    # --- New column on tasks ---
    op.add_column(
        "tasks",
        sa.Column(
            "pipeline_status",
            sa.Unicode(50),
            nullable=False,
            server_default="backlog",
        ),
    )

    # --- New table: task_pipeline_logs ---
    op.create_table(
        "task_pipeline_logs",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("task_id", _uuid_col(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("from_status", sa.Unicode(50), nullable=False),
        sa.Column("to_status", sa.Unicode(50), nullable=False),
        sa.Column("actor", sa.Unicode(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- New table: custom_roles ---
    op.create_table(
        "custom_roles",
        sa.Column("name", sa.Unicode(255), nullable=False),
        sa.Column(
            "definition",
            _json_col(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("name"),
    )

    # --- New table: custom_archetypes ---
    op.create_table(
        "custom_archetypes",
        sa.Column("name", sa.Unicode(255), nullable=False),
        sa.Column(
            "definition",
            _json_col(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    """Remove pipeline-related tables and columns."""
    # Drop tables first
    op.drop_table("custom_archetypes")
    op.drop_table("custom_roles")
    op.drop_table("task_pipeline_logs")

    # Drop FK before column on sessions — use batch mode for SQLite compat.
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_constraint("fk_sessions_task_id", type_="foreignkey")

    # Drop columns from tasks
    op.drop_column("tasks", "pipeline_status")

    # Drop columns from sessions (reverse order of add)
    op.drop_column("sessions", "pipeline_step")
    op.drop_column("sessions", "task_id")
    op.drop_column("sessions", "role")
