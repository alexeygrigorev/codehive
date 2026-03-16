"""SQLAlchemy 2.0 declarative models for all core entities."""

import uuid
from datetime import datetime

from datetime import timezone as tz

from sqlalchemy import Boolean, ForeignKey, Integer, Text, Unicode, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Unicode(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(Unicode(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Unicode(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(tz.utc),
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Unicode(255), unique=True, nullable=False)
    root_path: Mapped[str] = mapped_column(Unicode(1024), nullable=False)
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    projects: Mapped[list["Project"]] = relationship(back_populates="workspace")
    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(tz.utc),
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    path: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    archetype: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)
    knowledge: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    github_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    workspace: Mapped["Workspace"] = relationship(back_populates="projects")
    issues: Mapped[list["Issue"]] = relationship(back_populates="project")
    sessions: Mapped[list["Session"]] = relationship(back_populates="project")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="open")
    github_issue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    project: Mapped["Project"] = relationship(back_populates="issues")
    sessions: Mapped[list["Session"]] = relationship(back_populates="issue")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id"), nullable=True
    )
    parent_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    engine: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    mode: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="idle")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    project: Mapped["Project"] = relationship(back_populates="sessions")
    issue: Mapped["Issue | None"] = relationship(back_populates="sessions")
    parent_session: Mapped["Session | None"] = relationship(
        remote_side=[id], back_populates="child_sessions"
    )
    child_sessions: Mapped[list["Session"]] = relationship(back_populates="parent_session")
    tasks: Mapped[list["Task"]] = relationship(back_populates="session")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")
    events: Mapped[list["Event"]] = relationship(back_populates="session")
    checkpoints: Mapped[list["Checkpoint"]] = relationship(back_populates="session")
    pending_questions: Mapped[list["PendingQuestion"]] = relationship(back_populates="session")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    depends_on: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    mode: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="auto")
    created_by: Mapped[str] = mapped_column(Unicode(50), nullable=False, server_default="user")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    session: Mapped["Session"] = relationship(back_populates="tasks")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    session: Mapped["Session"] = relationship(back_populates="messages")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    session: Mapped["Session"] = relationship(back_populates="events")


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    git_ref: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    session: Mapped["Session"] = relationship(back_populates="checkpoints")


class PendingQuestion(Base):
    __tablename__ = "pending_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    session: Mapped["Session"] = relationship(back_populates="pending_questions")


class RemoteTarget(Base):
    __tablename__ = "remote_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
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
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    workspace: Mapped["Workspace"] = relationship()


class CustomRole(Base):
    __tablename__ = "custom_roles"

    name: Mapped[str] = mapped_column(Unicode(255), primary_key=True)
    definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class CustomArchetype(Base):
    __tablename__ = "custom_archetypes"

    name: Mapped[str] = mapped_column(Unicode(255), primary_key=True)
    definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(tz.utc),
    )


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(tz.utc),
    )
