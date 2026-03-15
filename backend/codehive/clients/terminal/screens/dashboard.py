"""Dashboard screen: summary counts, active projects, recent sessions."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from codehive.clients.terminal.widgets.data_table import StyledDataTable


class SummaryCard(Static):
    """A small card showing a label and a numeric value."""

    DEFAULT_CSS = """
    SummaryCard {
        width: 1fr;
        height: 5;
        border: solid $primary;
        padding: 1 2;
        text-align: center;
    }
    """

    def __init__(self, label: str, value: int = 0, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._label = label
        self._value = value

    def compose(self) -> ComposeResult:
        yield Static(f"{self._label}\n[b]{self._value}[/b]")

    def update_value(self, value: int) -> None:
        self._value = value
        self.query_one(Static).update(f"{self._label}\n[b]{self._value}[/b]")


class DashboardScreen(Screen):
    """Main dashboard showing summary counts and a project list."""

    BINDINGS = [
        ("p", "show_projects", "Projects"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    #summary-row {
        height: auto;
        padding: 1;
    }
    #projects-label {
        padding: 1 1 0 1;
    }
    #no-projects {
        padding: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            with Horizontal(id="summary-row"):
                yield SummaryCard("Projects", id="card-projects")
                yield SummaryCard("Active Sessions", id="card-active")
                yield SummaryCard("Pending Questions", id="card-questions")
                yield SummaryCard("Failed Sessions", id="card-failed")
            yield Static("Projects", id="projects-label")
            yield StyledDataTable(id="projects-table")
            yield Static("", id="no-projects")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#projects-table", StyledDataTable)
        table.add_columns("Name", "Sessions")
        table.cursor_type = "row"
        self.query_one("#no-projects").display = False
        self._load_data()

    @work(thread=True)
    def _load_data(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            projects = api.list_projects()
        except Exception:
            projects = []

        # Gather session and question counts
        all_sessions: list[dict] = []
        pending_questions = 0
        project_session_counts: dict[str, int] = {}
        for proj in projects:
            pid = proj["id"]
            try:
                sessions = api.list_sessions(pid)
            except Exception:
                sessions = []
            project_session_counts[pid] = len(sessions)
            all_sessions.extend(sessions)

            for sess in sessions:
                try:
                    questions = api.list_questions(sess["id"], answered=False)
                    pending_questions += len(questions)
                except Exception:
                    pass

        active = sum(1 for s in all_sessions if s.get("status") not in ("completed", "failed"))
        failed = sum(1 for s in all_sessions if s.get("status") == "failed")

        self.app.call_from_thread(
            self._apply_data, projects, project_session_counts, active, pending_questions, failed
        )

    def _apply_data(
        self,
        projects: list[dict],
        session_counts: dict[str, int],
        active: int,
        pending: int,
        failed: int,
    ) -> None:
        self.query_one("#card-projects", SummaryCard).update_value(len(projects))
        self.query_one("#card-active", SummaryCard).update_value(active)
        self.query_one("#card-questions", SummaryCard).update_value(pending)
        self.query_one("#card-failed", SummaryCard).update_value(failed)

        table = self.query_one("#projects-table", StyledDataTable)
        table.clear()
        if not projects:
            self.query_one("#no-projects").update("No projects found.")
            self.query_one("#no-projects").display = True
            table.display = False
        else:
            self.query_one("#no-projects").display = False
            table.display = True
            for proj in projects:
                count = session_counts.get(proj["id"], 0)
                table.add_row(proj["name"], str(count), key=proj["id"])

    def on_data_table_row_selected(self, event: StyledDataTable.RowSelected) -> None:
        from codehive.clients.terminal.screens.project_detail import ProjectDetailScreen

        self.app.push_screen(ProjectDetailScreen(str(event.row_key.value)))

    def action_show_projects(self) -> None:
        from codehive.clients.terminal.screens.project_list import ProjectListScreen

        self.app.push_screen(ProjectListScreen())

    def action_quit(self) -> None:
        self.app.exit()
