"""Full project list screen with navigation to project detail."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from codehive.clients.terminal.widgets.data_table import StyledDataTable


class ProjectListScreen(Screen):
    """Table of all projects with selection to navigate to detail."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    #pl-title {
        padding: 1;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("All Projects", id="pl-title")
        yield StyledDataTable(id="pl-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#pl-table", StyledDataTable)
        table.add_columns("Name", "Path", "Description", "Created")
        table.cursor_type = "row"
        self._load_data()

    @work(thread=True)
    def _load_data(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            projects = api.list_projects()
        except Exception:
            projects = []
        self.app.call_from_thread(self._apply_data, projects)

    def _apply_data(self, projects: list[dict]) -> None:
        table = self.query_one("#pl-table", StyledDataTable)
        table.clear()
        for proj in projects:
            desc = proj.get("description") or ""
            if len(desc) > 40:
                desc = desc[:37] + "..."
            table.add_row(
                proj.get("name", ""),
                proj.get("path") or "",
                desc,
                proj.get("created_at", ""),
                key=proj["id"],
            )

    def on_data_table_row_selected(self, event: StyledDataTable.RowSelected) -> None:
        from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

        self.app.push_screen(ProjectDetailScreen(str(event.row_key.value)))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
