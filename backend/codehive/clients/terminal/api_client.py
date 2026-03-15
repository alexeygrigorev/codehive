"""Thin httpx wrapper for TUI screens to talk to the backend API."""

from __future__ import annotations

from typing import Any

import httpx


class APIClient:
    """Synchronous HTTP client for the codehive REST API.

    Textual has its own async model; HTTP calls should be dispatched via
    ``run_worker`` so the UI thread is never blocked.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)

    # -- low-level ---------------------------------------------------------

    def get(self, path: str, **params: Any) -> Any:
        """GET *path* and return parsed JSON.

        Raises ``httpx.ConnectError`` when the server is unreachable and
        ``httpx.HTTPStatusError`` on 4xx/5xx responses.
        """
        resp = self._client.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    # -- convenience helpers -----------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        return self.get("/api/projects")

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.get(f"/api/projects/{project_id}")

    def list_sessions(self, project_id: str) -> list[dict[str, Any]]:
        return self.get(f"/api/projects/{project_id}/sessions")

    def list_questions(self, session_id: str, answered: bool | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if answered is not None:
            params["answered"] = str(answered).lower()
        return self.get(f"/api/sessions/{session_id}/questions", **params)

    def post(self, path: str, json: Any = None) -> Any:
        """POST *path* with a JSON body and return parsed JSON.

        Raises ``httpx.ConnectError`` when the server is unreachable and
        ``httpx.HTTPStatusError`` on 4xx/5xx responses.
        """
        resp = self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    # -- session helpers ---------------------------------------------------

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.get(f"/api/sessions/{session_id}")

    def list_tasks(self, session_id: str) -> list[dict[str, Any]]:
        return self.get(f"/api/sessions/{session_id}/tasks")

    def list_events(
        self, session_id: str, limit: int | None = None, offset: int | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self.get(f"/api/sessions/{session_id}/events", **params)

    def get_diffs(self, session_id: str) -> list[dict[str, Any]]:
        return self.get(f"/api/sessions/{session_id}/diffs")

    def post_message(self, session_id: str, content: str) -> dict[str, Any]:
        return self.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": content},
        )

    def build_url(self, path: str) -> str:
        """Return the full URL for a given API path."""
        return f"{self.base_url}{path}"
