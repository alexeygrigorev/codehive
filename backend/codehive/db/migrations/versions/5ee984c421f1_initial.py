"""initial

Revision ID: 5ee984c421f1
Revises:
Create Date: 2026-03-14 22:49:52.765002

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5ee984c421f1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_col():
    """Return a JSON column type that works on both PostgreSQL and SQLite."""
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    return sa.JSON().with_variant(PG_JSONB(), "postgresql")


def _uuid_col():
    """Return a UUID-compatible column type for both dialects."""
    return sa.String(36)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workspaces",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("name", sa.Unicode(length=255), nullable=False),
        sa.Column("root_path", sa.Unicode(length=1024), nullable=False),
        sa.Column(
            "settings",
            _json_col(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "projects",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("workspace_id", _uuid_col(), nullable=False),
        sa.Column("name", sa.Unicode(length=255), nullable=False),
        sa.Column("path", sa.Unicode(length=1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("archetype", sa.Unicode(length=100), nullable=True),
        sa.Column(
            "knowledge",
            _json_col(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "issues",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("project_id", _uuid_col(), nullable=False),
        sa.Column("title", sa.Unicode(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Unicode(length=50), server_default="open", nullable=False),
        sa.Column("github_issue_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("project_id", _uuid_col(), nullable=False),
        sa.Column("issue_id", _uuid_col(), nullable=True),
        sa.Column("parent_session_id", _uuid_col(), nullable=True),
        sa.Column("name", sa.Unicode(length=255), nullable=False),
        sa.Column("engine", sa.Unicode(length=50), nullable=False),
        sa.Column("mode", sa.Unicode(length=50), nullable=False),
        sa.Column("status", sa.Unicode(length=50), server_default="idle", nullable=False),
        sa.Column(
            "config",
            _json_col(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["issues.id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_session_id"],
            ["sessions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("session_id", _uuid_col(), nullable=False),
        sa.Column("git_ref", sa.Unicode(length=255), nullable=False),
        sa.Column(
            "state",
            _json_col(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "events",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("session_id", _uuid_col(), nullable=False),
        sa.Column("type", sa.Unicode(length=100), nullable=False),
        sa.Column(
            "data",
            _json_col(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("session_id", _uuid_col(), nullable=False),
        sa.Column("role", sa.Unicode(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            _json_col(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pending_questions",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("session_id", _uuid_col(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("answered", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("session_id", _uuid_col(), nullable=False),
        sa.Column("title", sa.Unicode(length=500), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("status", sa.Unicode(length=50), server_default="pending", nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("depends_on", _uuid_col(), nullable=True),
        sa.Column("mode", sa.Unicode(length=50), server_default="auto", nullable=False),
        sa.Column("created_by", sa.Unicode(length=50), server_default="user", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tasks")
    op.drop_table("pending_questions")
    op.drop_table("messages")
    op.drop_table("events")
    op.drop_table("checkpoints")
    op.drop_table("sessions")
    op.drop_table("issues")
    op.drop_table("projects")
    op.drop_table("workspaces")
