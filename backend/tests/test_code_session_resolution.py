"""Tests for session resolution in `codehive code` command."""

from __future__ import annotations

import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from codehive.cli import _resolve_project_and_session, main


def _run_cli(args: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, int]:
    """Run the CLI with given args, return (stdout, stderr, exit_code)."""
    monkeypatch.setattr("sys.argv", ["codehive"] + args)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    err = StringIO()
    monkeypatch.setattr("sys.stderr", err)
    try:
        main()
        return out.getvalue(), err.getvalue(), 0
    except SystemExit as e:
        return out.getvalue(), err.getvalue(), e.code if e.code is not None else 0


def _make_mock_client(
    project_id: str,
    sessions: list[dict] | None = None,
    create_session_id: str | None = None,
) -> MagicMock:
    """Create a mock httpx.Client with by-path and sessions responses."""
    mock_client = MagicMock(spec=httpx.Client)

    by_path_resp = MagicMock()
    by_path_resp.status_code = 200
    by_path_resp.json.return_value = {"id": project_id, "name": "test-project"}

    sessions_resp = MagicMock()
    sessions_resp.status_code = 200
    sessions_resp.json.return_value = sessions if sessions is not None else []

    create_resp = MagicMock()
    create_resp.status_code = 201
    create_resp.json.return_value = {
        "id": create_session_id or str(uuid.uuid4()),
        "name": "code-session",
    }

    def post_side_effect(path: str, **kwargs):
        if "by-path" in path:
            return by_path_resp
        return create_resp

    mock_client.post.side_effect = post_side_effect
    mock_client.get.return_value = sessions_resp

    return mock_client


class TestSessionResolution:
    def test_picks_most_recent_session(self) -> None:
        """When multiple sessions exist, picks the one with the most recent created_at."""
        project_id = str(uuid.uuid4())
        s1 = str(uuid.uuid4())
        s2 = str(uuid.uuid4())
        s3 = str(uuid.uuid4())

        sessions = [
            {"id": s1, "created_at": "2026-01-01T00:00:00"},
            {"id": s3, "created_at": "2026-03-01T00:00:00"},
            {"id": s2, "created_at": "2026-02-01T00:00:00"},
        ]

        mock_client = _make_mock_client(project_id, sessions=sessions)

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            pid, sid = _resolve_project_and_session(
                "http://localhost:7433", "/some/dir", None, False
            )

        assert pid == project_id
        assert sid == s3  # Most recent

    def test_empty_sessions_creates_new(self) -> None:
        """When no sessions exist, creates one via POST."""
        project_id = str(uuid.uuid4())
        new_session_id = str(uuid.uuid4())

        mock_client = _make_mock_client(project_id, sessions=[], create_session_id=new_session_id)

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            pid, sid = _resolve_project_and_session(
                "http://localhost:7433", "/some/dir", None, False
            )

        assert pid == project_id
        assert sid == new_session_id

        # Verify POST was called to create session (second post call after by-path)
        post_calls = mock_client.post.call_args_list
        assert len(post_calls) == 2  # by-path + create session
        create_call = post_calls[1]
        assert f"/api/projects/{project_id}/sessions" in create_call[0][0]
        body = create_call[1]["json"]
        assert body["name"] == "code-session"
        assert body["engine"] == "native"
        assert body["mode"] == "execution"

    def test_session_flag_uses_uuid_directly(self) -> None:
        """--session <uuid> uses that UUID directly, no GET or POST to sessions API."""
        project_id = str(uuid.uuid4())
        explicit_session = str(uuid.uuid4())

        mock_client = _make_mock_client(project_id)

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            pid, sid = _resolve_project_and_session(
                "http://localhost:7433", "/some/dir", explicit_session, False
            )

        assert pid == project_id
        assert sid == explicit_session

        # No GET call for sessions list
        mock_client.get.assert_not_called()

        # Only one POST call (by-path), no session create
        post_calls = mock_client.post.call_args_list
        assert len(post_calls) == 1

    def test_new_flag_creates_session(self) -> None:
        """--new flag creates a new session via POST, no GET call."""
        project_id = str(uuid.uuid4())
        new_session_id = str(uuid.uuid4())

        mock_client = _make_mock_client(project_id, create_session_id=new_session_id)

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            pid, sid = _resolve_project_and_session(
                "http://localhost:7433", "/some/dir", None, True
            )

        assert pid == project_id
        assert sid == new_session_id

        # No GET call for sessions list
        mock_client.get.assert_not_called()

    def test_session_and_new_mutually_exclusive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--session and --new cannot be used together."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            _, stderr, code = _run_cli(
                ["code", "--session", str(uuid.uuid4()), "--new", tmpdir],
                monkeypatch,
            )
            assert code != 0
