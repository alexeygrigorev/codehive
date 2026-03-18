"""Tests for project resolution in `codehive code` command."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from codehive.cli import _resolve_project_and_session


class TestProjectResolution:
    def test_by_path_called_with_absolute_path(self) -> None:
        """POST /api/projects/by-path is called with the absolute project directory."""
        project_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        mock_client = MagicMock(spec=httpx.Client)

        # by-path response
        by_path_resp = MagicMock()
        by_path_resp.status_code = 200
        by_path_resp.json.return_value = {"id": project_id, "name": "test-project"}

        # sessions list response
        sessions_resp = MagicMock()
        sessions_resp.status_code = 200
        sessions_resp.json.return_value = [{"id": session_id, "created_at": "2026-01-01T00:00:00"}]

        mock_client.post.return_value = by_path_resp
        mock_client.get.return_value = sessions_resp

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            pid, sid = _resolve_project_and_session(
                "http://localhost:7433", "/absolute/project/dir", None, False
            )

        assert pid == project_id
        mock_client.post.assert_called_once_with(
            "/api/projects/by-path", json={"path": "/absolute/project/dir"}
        )

    def test_by_path_error_falls_back(self) -> None:
        """Error from by-path API falls back to local mode."""
        mock_client = MagicMock(spec=httpx.Client)

        error_resp = MagicMock()
        error_resp.status_code = 500
        mock_client.post.return_value = error_resp

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            with pytest.raises(SystemExit):
                _resolve_project_and_session("http://localhost:7433", "/some/path", None, False)

    def test_by_path_returns_project_id(self) -> None:
        """Response project ID is extracted and used for session lookup."""
        project_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        mock_client = MagicMock(spec=httpx.Client)

        by_path_resp = MagicMock()
        by_path_resp.status_code = 200
        by_path_resp.json.return_value = {"id": project_id, "name": "my-project"}

        sessions_resp = MagicMock()
        sessions_resp.status_code = 200
        sessions_resp.json.return_value = [{"id": session_id, "created_at": "2026-03-18T00:00:00"}]

        mock_client.post.return_value = by_path_resp
        mock_client.get.return_value = sessions_resp

        with patch("codehive.cli.httpx.Client", return_value=mock_client):
            pid, sid = _resolve_project_and_session(
                "http://localhost:7433", "/my/project", None, False
            )

        assert pid == project_id
        assert sid == session_id
        # Verify sessions list was called with the resolved project_id
        mock_client.get.assert_called_once_with(f"/api/projects/{project_id}/sessions")
