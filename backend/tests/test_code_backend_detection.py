"""Tests for backend detection in `codehive code` command."""

from __future__ import annotations

import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from codehive.cli import _probe_backend, main


def _run_cli(args: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, int]:
    """Run the CLI with given args, capture stdout/stderr, return (stdout, stderr, exit_code)."""
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


class TestProbeBackend:
    def test_health_200_returns_true(self) -> None:
        """Health endpoint returning 200 -> backend is available."""
        with patch("codehive.cli.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            assert _probe_backend("http://localhost:7433") is True

    def test_health_500_returns_false(self) -> None:
        """Health endpoint returning 500 -> backend not available."""
        with patch("codehive.cli.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_get.return_value = mock_resp
            assert _probe_backend("http://localhost:7433") is False

    def test_connect_error_returns_false(self) -> None:
        """Connection error -> backend not available."""
        with patch("codehive.cli.httpx.get", side_effect=httpx.ConnectError("refused")):
            assert _probe_backend("http://localhost:7433") is False

    def test_timeout_returns_false(self) -> None:
        """Timeout -> backend not available."""
        with patch("codehive.cli.httpx.get", side_effect=httpx.TimeoutException("timeout")):
            assert _probe_backend("http://localhost:7433") is False


class TestCodeBackendDetection:
    def test_backend_available_enters_backend_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """When health returns 200 and by-path succeeds, CodeApp is created with backend_url."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())

            with (
                patch("codehive.cli._probe_backend", return_value=True),
                patch(
                    "codehive.cli._resolve_project_and_session",
                    return_value=(project_id, session_id),
                ),
                patch("codehive.clients.terminal.code_app.CodeApp") as mock_app_cls,
            ):
                mock_app_cls.return_value = MagicMock()
                _run_cli(["code", tmpdir], monkeypatch)

                mock_app_cls.assert_called_once()
                call_kwargs = mock_app_cls.call_args[1]
                assert call_kwargs["backend_url"] is not None
                assert call_kwargs["project_id"] == uuid.UUID(project_id)
                assert call_kwargs["session_id"] == uuid.UUID(session_id)

    def test_backend_unavailable_local_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When health probe fails, falls back to local mode with warning."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("codehive.cli._probe_backend", return_value=False),
                patch("codehive.cli._resolve_provider", return_value=("sk-test", "", "model")),
                patch("codehive.clients.terminal.code_app.CodeApp") as mock_app_cls,
            ):
                mock_app_cls.return_value = MagicMock()
                _, stderr, _ = _run_cli(["code", tmpdir], monkeypatch)

                mock_app_cls.assert_called_once()
                call_kwargs = mock_app_cls.call_args[1]
                assert "backend_url" not in call_kwargs or call_kwargs.get("backend_url") is None
                assert "Backend not available" in stderr

    def test_backend_unavailable_no_api_key_uses_claude_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When backend unavailable and no API key, falls back to Claude CLI (no error)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("codehive.cli._probe_backend", return_value=False),
                patch("codehive.cli._resolve_provider", return_value=("", "", "")),
                patch("codehive.clients.terminal.code_app.CodeApp") as mock_app_cls,
            ):
                mock_app_cls.return_value = MagicMock()
                _, stderr, code = _run_cli(["code", tmpdir], monkeypatch)
                assert code == 0
                mock_app_cls.assert_called_once()
                call_kwargs = mock_app_cls.call_args[1]
                assert call_kwargs.get("api_key") == ""
