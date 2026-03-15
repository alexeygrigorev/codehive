"""Textual App subclass -- main entry point for the TUI."""

from __future__ import annotations

from textual.app import App

from codehive.clients.terminal.api_client import APIClient
from codehive.clients.terminal.screens.dashboard import DashboardScreen


class CodehiveApp(App):
    """Codehive terminal dashboard application."""

    TITLE = "Codehive"
    SUB_TITLE = "Agent Workspace"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, base_url: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.api_client = APIClient(base_url)

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())
