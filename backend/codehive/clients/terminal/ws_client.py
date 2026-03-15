"""WebSocket client for live session event streaming."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import websockets.sync.client as ws_sync

logger = logging.getLogger(__name__)


class WSClient:
    """Synchronous WebSocket client that connects to a session event stream.

    Designed to run inside a Textual ``@work(thread=True)`` worker so it
    does not block the UI thread.
    """

    def __init__(self, base_url: str, session_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._session_id = session_id
        self._running = False

    @property
    def ws_url(self) -> str:
        """Build the WebSocket URL from the HTTP base URL."""
        url = self._base_url
        if url.startswith("https://"):
            url = "wss://" + url[len("https://") :]
        elif url.startswith("http://"):
            url = "ws://" + url[len("http://") :]
        return f"{url}/api/sessions/{self._session_id}/ws"

    def connect(self, on_event: Callable[[dict[str, Any]], None]) -> None:
        """Connect and dispatch events until stopped or disconnected.

        *on_event* is called for each JSON message received from the server.
        The caller is responsible for thread-safety (e.g. using
        ``app.call_from_thread``).
        """
        self._running = True
        try:
            with ws_sync.connect(self.ws_url) as conn:
                while self._running:
                    try:
                        raw = conn.recv(timeout=1.0)
                    except TimeoutError:
                        continue
                    try:
                        data = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    on_event(data)
        except Exception:
            logger.debug("WebSocket connection closed for session %s", self._session_id)

    def stop(self) -> None:
        """Signal the client to disconnect."""
        self._running = False
