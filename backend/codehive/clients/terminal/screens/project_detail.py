"""Project detail screen: name, description, sessions list."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from codehive.clients.terminal.widgets.data_table import StyledDataTable


class ProjectDetailScreen(Screen):
    """Shows a single project with its sessions."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    #pd-name {
        padding: 1;
        text-style: bold;
    }
    #pd-desc {
        padding: 0 1 1 1;
        color: $text-muted;
    }
    #pd-sessions-label {
        padding: 1 1 0 1;
    }
    """

    def __init__(self, project_id: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._project_id = project_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Loading...", id="pd-name")
        yield Static("", id="pd-desc")
        yield Static("Sessions", id="pd-sessions-label")
        yield StyledDataTable(id="pd-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#pd-table", StyledDataTable)
        table.add_columns("Name", "Engine", "Mode", "Status")
        table.cursor_type = "row"
        self._load_data()

    @work(thread=True)
    def _load_data(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            project = api.get_project(self._project_id)
        except Exception:
            project = {"name": "Error", "description": "Could not load project"}
        try:
            sessions = api.list_sessions(self._project_id)
        except Exception:
            sessions = []
        self.app.call_from_thread(self._apply_data, project, sessions)

    def _apply_data(self, project: dict, sessions: list[dict]) -> None:
        self.query_one("#pd-name", Static).update(project.get("name", ""))
        self.query_one("#pd-desc", Static).update(project.get("description") or "")

        table = self.query_one("#pd-table", StyledDataTable)
        table.clear()
        for sess in sessions:
            table.add_row(
                sess.get("name", ""),
                sess.get("engine", ""),
                sess.get("mode", ""),
                sess.get("status", ""),
                key=sess["id"],
            )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
