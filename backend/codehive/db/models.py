"""SQLAlchemy 2.0 declarative models for all core entities.

All column types are portable across PostgreSQL and SQLite:
- PortableUUID: UUID on PostgreSQL, CHAR(36) on SQLite
- PortableJSON: JSONB on PostgreSQL, JSON on SQLite
- server_default=text("CURRENT_TIMESTAMP") instead of text("now()")
- server_default=text("'{}'") instead of text("'{}'::jsonb")
- Boolean server defaults use literal '1'/'0' (portable)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, Unicode, text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class PortableUUID(TypeDecorator):
    """UUID type that works on both PostgreSQL (native UUID) and SQLite (CHAR(36))."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value


# Portable JSON: JSONB on PostgreSQL, plain JSON on SQLite
PortableJSON = JSON().with_variant(PG_JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Shared declarative base for all models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Unicode(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(Unicode(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Unicode(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    path: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    archetype: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)
    knowledge: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, server_default=text("'{}'")
    )
    github_config: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    issues: Mapped[list["Issue"]] = relationship(back_populates="project")
    sessions: Mapped[list["Session"]] = relationship(back_populates="project")
    team: Mapped[list["AgentProfile"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    role: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    avatar_seed: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt_modifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    project: Mapped["Project"] = relationship(back_populates="team")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_agent: Mapped[str | None] = mapped_column(Unicode(50), nullable=True)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="open")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    github_issue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    project: Mapped["Project"] = relationship(back_populates="issues")
    sessions: Mapped[list["Session"]] = relationship(back_populates="issue")
    logs: Mapped[list["IssueLogEntry"]] = relationship(
        back_populates="issue", order_by="IssueLogEntry.created_at.asc()"
    )


class IssueLogEntry(Base):
    __tablename__ = "issue_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("issues.id"), nullable=False
    )
    agent_role: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("agent_profiles.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    issue: Mapped["Issue"] = relationship(back_populates="logs")
    agent_profile: Mapped["AgentProfile | None"] = relationship()


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("projects.id"), nullable=False
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("issues.id"), nullable=True
    )
    parent_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    role: Mapped[str | None] = mapped_column(Unicode(50), nullable=True)
    engine: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    mode: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="idle")
    config: Mapped[dict] = mapped_column(PortableJSON, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    project: Mapped["Project"] = relationship(back_populates="sessions")
    issue: Mapped["Issue | None"] = relationship(back_populates="sessions")
    parent_session: Mapped["Session | None"] = relationship(
        remote_side=[id], back_populates="child_sessions"
    )
    child_sessions: Mapped[list["Session"]] = relationship(back_populates="parent_session")
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("tasks.id", use_alter=True), nullable=True
    )
    pipeline_step: Mapped[str | None] = mapped_column(Unicode(50), nullable=True)
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("agent_profiles.id"), nullable=True
    )

    agent_profile: Mapped["AgentProfile | None"] = relationship()
    bound_task: Mapped["Task | None"] = relationship(
        foreign_keys="Session.task_id", back_populates="agent_sessions"
    )
    tasks: Mapped[list["Task"]] = relationship(
        foreign_keys="Task.session_id", back_populates="session"
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="session")
    events: Mapped[list["Event"]] = relationship(back_populates="session")
    checkpoints: Mapped[list["Checkpoint"]] = relationship(back_populates="session")
    pending_questions: Mapped[list["PendingQuestion"]] = relationship(back_populates="session")
    usage_records: Mapped[list["UsageRecord"]] = relationship(back_populates="session")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    depends_on: Mapped[uuid.UUID | None] = mapped_column(PortableUUID, nullable=True)
    mode: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="auto")
    created_by: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="user")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    pipeline_status: Mapped[str] = mapped_column(
        Unicode(50), nullable=False, server_default="backlog"
    )

    session: Mapped["Session"] = relationship(
        foreign_keys="Task.session_id",
        back_populates="tasks",
    )
    agent_sessions: Mapped[list["Session"]] = relationship(
        foreign_keys="Session.task_id", back_populates="bound_task"
    )
    pipeline_logs: Mapped[list["TaskPipelineLog"]] = relationship(back_populates="task")


class TaskPipelineLog(Base):
    __tablename__ = "task_pipeline_logs"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(PortableUUID, ForeignKey("tasks.id"), nullable=False)
    from_status: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    to_status: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    actor: Mapped[str | None] = mapped_column(Unicode(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    task: Mapped["Task"] = relationship(back_populates="pipeline_logs")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", PortableJSON, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    session: Mapped["Session"] = relationship(back_populates="messages")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    data: Mapped[dict] = mapped_column(PortableJSON, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    session: Mapped["Session"] = relationship(back_populates="events")


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=False
    )
    git_ref: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    state: Mapped[dict] = mapped_column(PortableJSON, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    session: Mapped["Session"] = relationship(back_populates="checkpoints")


class PendingQuestion(Base):
    __tablename__ = "pending_questions"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    session: Mapped["Session"] = relationship(back_populates="pending_questions")


class RemoteTarget(Base):
    __tablename__ = "remote_targets"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    host: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("22"))
    username: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    key_path: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)
    known_hosts_policy: Mapped[str] = mapped_column(
        Unicode(50), nullable=False, server_default="auto"
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="disconnected")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CustomRole(Base):
    __tablename__ = "custom_roles"

    name: Mapped[str] = mapped_column(Unicode(255), primary_key=True)
    definition: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CustomArchetype(Base):
    __tablename__ = "custom_archetypes"

    name: Mapped[str] = mapped_column(Unicode(255), primary_key=True)
    definition: Mapped[dict] = mapped_column(
        PortableJSON, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=False
    )
    model: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    session: Mapped["Session"] = relationship(back_populates="usage_records")


class RateLimitSnapshot(Base):
    __tablename__ = "rate_limit_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=True
    )
    rate_limit_type: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    utilization: Mapped[float] = mapped_column(Float, nullable=False)
    resets_at: Mapped[int] = mapped_column(Integer, nullable=False)
    is_using_overage: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    surpassed_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class ModelUsageSnapshot(Base):
    __tablename__ = "model_usage_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("sessions.id"), nullable=True
    )
    model: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    cache_creation_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PortableUUID, ForeignKey("users.id"), nullable=True
    )
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
