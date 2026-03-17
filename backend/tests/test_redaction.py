"""Tests for secrets redaction: SecretRedactor, ShellRunner integration, EventBus integration."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.core.events import EventBus
from codehive.core.redaction import SecretRedactor
from codehive.db.models import Base, Project, Workspace
from codehive.db.models import Session as SessionModel
from codehive.execution.shell import ShellRunner

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database (same pattern as test_events.py)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def workspace(db_session: AsyncSession) -> Workspace:
    ws = Workspace(
        name="test-workspace",
        root_path="/tmp/test",
        settings={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    return ws


@pytest_asyncio.fixture
async def project(db_session: AsyncSession, workspace: Workspace) -> Project:
    proj = Project(
        workspace_id=workspace.id,
        name="test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def session_model(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest_asyncio.fixture
async def event_bus(mock_redis: AsyncMock) -> EventBus:
    return EventBus(redis=mock_redis)


# ===========================================================================
# Unit: SecretRedactor -- explicit values
# ===========================================================================


class TestSecretRedactorExplicit:
    def test_redact_known_secret(self):
        r = SecretRedactor(secrets=["sk-proj-abc123xyz"])
        result = r.redact("My key is sk-proj-abc123xyz ok")
        assert "sk-proj-abc123xyz" not in result
        assert "***REDACTED***" in result

    def test_redact_multiple_secrets(self):
        r = SecretRedactor(secrets=["secret-one-value", "secret-two-value"])
        text = "first=secret-one-value second=secret-two-value"
        result = r.redact(text)
        assert "secret-one-value" not in result
        assert "secret-two-value" not in result
        assert result.count("***REDACTED***") == 2

    def test_short_secrets_ignored(self):
        r = SecretRedactor(secrets=["", "ab", "xyz"])
        result = r.redact("ab xyz hello")
        # Empty and <=3 char secrets should not be redacted
        assert result == "ab xyz hello"

    def test_no_secrets_unchanged(self):
        r = SecretRedactor(secrets=["my-secret-value-1234"])
        result = r.redact("nothing sensitive here")
        assert result == "nothing sensitive here"

    def test_secret_appears_multiple_times(self):
        r = SecretRedactor(secrets=["supersecretvalue"])
        text = "a=supersecretvalue b=supersecretvalue"
        result = r.redact(text)
        assert "supersecretvalue" not in result
        assert result.count("***REDACTED***") == 2


# ===========================================================================
# Unit: SecretRedactor -- pattern-based detection
# ===========================================================================


class TestSecretRedactorPatterns:
    def test_anthropic_key(self):
        r = SecretRedactor()
        text = "key=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        result = r.redact(text)
        assert "sk-ant-api03-XXXX" not in result
        assert "REDACTED" in result

    def test_github_pat(self):
        r = SecretRedactor()
        text = "token=ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
        result = r.redact(text)
        assert "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345" not in result
        assert "REDACTED" in result

    def test_aws_access_key(self):
        r = SecretRedactor()
        text = "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF"
        result = r.redact(text)
        assert "AKIA1234567890ABCDEF" not in result
        assert "REDACTED" in result

    def test_url_embedded_password(self):
        r = SecretRedactor()
        text = "DATABASE_URL=postgres://user:s3cret@host/db"
        result = r.redact(text)
        assert "s3cret" not in result
        assert "REDACTED" in result

    def test_bearer_jwt_token(self):
        r = SecretRedactor()
        text = "Authorization: Bearer eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM"
        result = r.redact(text)
        assert "eyJhbGciOi" not in result
        assert "REDACTED" in result

    def test_env_var_assignment(self):
        r = SecretRedactor()
        text = "export API_KEY=somevalue123"
        result = r.redact(text)
        assert "somevalue123" not in result
        assert "REDACTED" in result

    def test_no_patterns_unchanged(self):
        r = SecretRedactor()
        text = "Just a normal log line with no secrets at all"
        result = r.redact(text)
        assert result == text


# ===========================================================================
# Unit: SecretRedactor -- deep dict redaction
# ===========================================================================


class TestSecretRedactorDeepDict:
    def test_flat_dict(self):
        r = SecretRedactor(secrets=["sk-abc123secret"])
        data = {"output": "key is sk-abc123secret"}
        result = r.redact_dict(data)
        assert "sk-abc123secret" not in result["output"]
        assert "REDACTED" in result["output"]

    def test_nested_dict(self):
        r = SecretRedactor()
        data = {"result": {"log": "token ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"}}
        result = r.redact_dict(data)
        assert "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345" not in result["result"]["log"]

    def test_list_values(self):
        r = SecretRedactor()
        data = {
            "lines": [
                "line1",
                "Authorization: Bearer eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM",
            ]
        }
        result = r.redact_dict(data)
        assert result["lines"][0] == "line1"
        assert "eyJhbGciOi" not in result["lines"][1]

    def test_non_string_values_unchanged(self):
        r = SecretRedactor(secrets=["mysecretvalue1234"])
        data = {"count": 42, "active": True, "nothing": None, "text": "mysecretvalue1234"}
        result = r.redact_dict(data)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["nothing"] is None
        assert "mysecretvalue1234" not in result["text"]


# ===========================================================================
# Integration: ShellRunner with redaction
# ===========================================================================


@pytest.mark.asyncio
class TestShellRunnerRedaction:
    async def test_run_redacts_stdout(self, tmp_path: Path):
        runner = ShellRunner()
        secret = "sk-proj-mysupersecretkey12345678"
        redactor = SecretRedactor(secrets=[secret])
        result = await runner.run(
            f"echo '{secret}'",
            working_dir=tmp_path,
            redactor=redactor,
        )
        assert secret not in result.stdout
        assert "REDACTED" in result.stdout

    async def test_run_redacts_stderr(self, tmp_path: Path):
        runner = ShellRunner()
        secret = "sk-proj-mysupersecretkey12345678"
        redactor = SecretRedactor(secrets=[secret])
        result = await runner.run(
            f"echo '{secret}' >&2",
            working_dir=tmp_path,
            redactor=redactor,
        )
        assert secret not in result.stderr
        assert "REDACTED" in result.stderr

    async def test_streaming_redacts_lines(self, tmp_path: Path):
        runner = ShellRunner()
        secret = "sk-proj-mysupersecretkey12345678"
        redactor = SecretRedactor(secrets=[secret])
        lines: list[str] = []
        async for line in runner.run_streaming(
            f"echo '{secret}'",
            working_dir=tmp_path,
            redactor=redactor,
        ):
            lines.append(line)
        assert len(lines) >= 1
        for line in lines:
            assert secret not in line

    async def test_run_without_redactor_unchanged(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("echo hello", working_dir=tmp_path)
        assert "hello" in result.stdout


# ===========================================================================
# Integration: EventBus with redaction
# ===========================================================================


@pytest.mark.asyncio
class TestEventBusRedaction:
    async def test_publish_redacts_data(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
        mock_redis: AsyncMock,
    ):
        secret = "sk-proj-mysupersecretkey12345678"
        redactor = SecretRedactor(secrets=[secret])
        ev = await event_bus.publish(
            db_session,
            session_model.id,
            "command.output",
            {"stdout": f"result: {secret}"},
            redactor=redactor,
        )
        # DB row must be redacted
        assert secret not in ev.data["stdout"]
        assert "REDACTED" in ev.data["stdout"]

        # Redis message must also be redacted
        call_args = mock_redis.publish.call_args
        msg = json.loads(call_args[0][1])
        assert secret not in msg["data"]["stdout"]

    async def test_publish_without_redactor_unchanged(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
    ):
        ev = await event_bus.publish(
            db_session,
            session_model.id,
            "message.created",
            {"content": "no secrets here"},
        )
        assert ev.data == {"content": "no secrets here"}
