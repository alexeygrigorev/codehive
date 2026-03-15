"""Rescue mode screen: failed sessions, pending questions, system health.

Designed for phone-over-SSH emergencies (minimum 80x24 terminal).
"""

from __future__ import annotations

from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from codehive.clients.terminal.api_client import APIClient
from codehive.clients.terminal.widgets.data_table import StyledDataTable


class HealthBanner(Static):
    """Single-line color-coded system health bar."""

    DEFAULT_CSS = """
    HealthBanner {
        height: 1;
        width: 100%;
        background: $surface;
    }
    HealthBanner.healthy {
        background: green 20%;
    }
    HealthBanner.degraded {
        background: red 20%;
    }
    """

    def set_health(self, data: dict[str, Any]) -> None:
        """Update the banner from health API response."""
        version = data.get("version", "?")
        db = data.get("database", "unknown")
        redis = data.get("redis", "unknown")
        active = data.get("active_sessions", 0)
        maint = data.get("maintenance", False)

        maint_label = " [MAINT]" if maint else ""
        text = f"v{version} | DB:{db} | Redis:{redis} | Active:{active}{maint_label}"
        self.update(text)

        is_healthy = db == "up" and redis == "up" and not maint
        self.remove_class("healthy", "degraded")
        self.add_class("healthy" if is_healthy else "degraded")


class RescueScreen(Screen):
    """Rescue mode: stop, rollback, answer, maintenance."""

    BINDINGS = [
        ("s", "stop_session", "Stop"),
        ("x", "restart_session", "Restart"),
        ("r", "rollback_session", "Rollback"),
        ("a", "answer_question", "Answer"),
        ("m", "toggle_maintenance", "Maint"),
        ("R", "refresh_data", "Refresh"),
        ("q", "quit_app", "Quit"),
        ("escape", "go_back", "Back"),
    ]

    DEFAULT_CSS = """
    #rescue-health {
        dock: top;
    }
    #rescue-sessions-label {
        padding: 1 1 0 1;
        text-style: bold;
    }
    #rescue-sessions-table {
        height: 8;
    }
    #rescue-no-sessions {
        padding: 0 1;
        color: $text-muted;
        display: none;
    }
    #rescue-questions-label {
        padding: 1 1 0 1;
        text-style: bold;
    }
    #rescue-questions-table {
        height: 1fr;
    }
    #rescue-no-questions {
        padding: 0 1;
        color: $text-muted;
        display: none;
    }
    #rescue-error {
        padding: 1;
        color: red;
        display: none;
    }
    #rescue-answer-input {
        display: none;
        dock: bottom;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._sessions_data: list[dict[str, Any]] = []
        self._questions_data: list[dict[str, Any]] = []
        self._health_data: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield HealthBanner(id="rescue-health")
        yield Static("Failed / Stuck Sessions", id="rescue-sessions-label")
        yield StyledDataTable(id="rescue-sessions-table")
        yield Static("No failed or stuck sessions.", id="rescue-no-sessions")
        yield Static("Pending Questions", id="rescue-questions-label")
        yield StyledDataTable(id="rescue-questions-table")
        yield Static("No pending questions.", id="rescue-no-questions")
        yield Static("", id="rescue-error")
        yield Input(placeholder="Type answer and press Enter...", id="rescue-answer-input")
        yield Footer()

    def on_mount(self) -> None:
        sessions_table = self.query_one("#rescue-sessions-table", StyledDataTable)
        sessions_table.add_columns("Name", "Status", "Project")
        sessions_table.cursor_type = "row"

        questions_table = self.query_one("#rescue-questions-table", StyledDataTable)
        questions_table.add_columns("Session", "Question")
        questions_table.cursor_type = "row"

        self._load_data()

    @work(thread=True)
    def _load_data(self) -> None:
        api: APIClient = self.app.api_client  # type: ignore[attr-defined]

        # Load system health
        health: dict[str, Any] = {}
        try:
            health = api.get_system_health()
        except Exception:
            health = {
                "version": "?",
                "database": "error",
                "redis": "error",
                "active_sessions": 0,
                "maintenance": False,
            }

        # Load all projects then sessions
        stuck_statuses = {"failed", "waiting_input", "blocked"}
        failed_sessions: list[dict[str, Any]] = []
        all_questions: list[dict[str, Any]] = []

        try:
            projects = api.list_projects()
        except Exception:
            projects = []

        for proj in projects:
            try:
                sessions = api.list_sessions(proj["id"])
            except Exception:
                sessions = []
            for sess in sessions:
                if sess.get("status") in stuck_statuses:
                    sess["_project_name"] = proj.get("name", "?")
                    failed_sessions.append(sess)
                # Load pending questions for each session
                try:
                    questions = api.list_questions(sess["id"], answered=False)
                    for q in questions:
                        q["_session_name"] = sess.get("name", "?")
                    all_questions.extend(questions)
                except Exception:
                    pass

        self.app.call_from_thread(self._apply_data, health, failed_sessions, all_questions)

    def _apply_data(
        self,
        health: dict[str, Any],
        sessions: list[dict[str, Any]],
        questions: list[dict[str, Any]],
    ) -> None:
        self._health_data = health
        self._sessions_data = sessions
        self._questions_data = questions

        # Hide error
        error_widget = self.query_one("#rescue-error", Static)
        error_widget.display = False

        # Update health banner
        self.query_one("#rescue-health", HealthBanner).set_health(health)

        # Update sessions table
        sessions_table = self.query_one("#rescue-sessions-table", StyledDataTable)
        sessions_table.clear()
        no_sessions = self.query_one("#rescue-no-sessions", Static)

        if sessions:
            no_sessions.display = False
            sessions_table.display = True
            for sess in sessions:
                name = sess.get("name", "?")
                status = sess.get("status", "?")
                project = sess.get("_project_name", "?")[:20]
                sessions_table.add_row(name, status, project, key=sess["id"])
        else:
            no_sessions.display = True
            sessions_table.display = False

        # Update questions table
        questions_table = self.query_one("#rescue-questions-table", StyledDataTable)
        questions_table.clear()
        no_questions = self.query_one("#rescue-no-questions", Static)

        if questions:
            no_questions.display = False
            questions_table.display = True
            for q in questions:
                session_name = q.get("_session_name", "?")
                question_text = q.get("question", "?")
                if len(question_text) > 50:
                    question_text = question_text[:47] + "..."
                questions_table.add_row(session_name, question_text, key=q["id"])
        else:
            no_questions.display = True
            questions_table.display = False

    def _show_error(self, msg: str) -> None:
        error_widget = self.query_one("#rescue-error", Static)
        error_widget.update(msg)
        error_widget.display = True

    def _get_selected_session_id(self) -> str | None:
        """Return the session ID of the selected row, or None."""
        table = self.query_one("#rescue-sessions-table", StyledDataTable)
        if not table.display or not self._sessions_data:
            return None
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            return str(row_key.value)
        except Exception:
            return None

    def _get_selected_question(self) -> dict[str, Any] | None:
        """Return the question dict of the selected row, or None."""
        table = self.query_one("#rescue-questions-table", StyledDataTable)
        if not table.display or not self._questions_data:
            return None
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            qid = str(row_key.value)
            return next((q for q in self._questions_data if q["id"] == qid), None)
        except Exception:
            return None

    # -- actions -----------------------------------------------------------

    def action_stop_session(self) -> None:
        session_id = self._get_selected_session_id()
        if session_id:
            self._do_pause(session_id)

    @work(thread=True)
    def _do_pause(self, session_id: str) -> None:
        api: APIClient = self.app.api_client  # type: ignore[attr-defined]
        try:
            api.pause_session(session_id)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Pause failed: {exc}")
            return
        # Reload data after action
        self._load_data()

    def action_restart_session(self) -> None:
        session_id = self._get_selected_session_id()
        if session_id:
            self._do_restart(session_id)

    @work(thread=True)
    def _do_restart(self, session_id: str) -> None:
        api: APIClient = self.app.api_client  # type: ignore[attr-defined]
        try:
            api.pause_session(session_id)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Restart failed: {exc}")
            return
        try:
            api.resume_session(session_id)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Restart failed: {exc}")
            return
        self._load_data()

    def action_rollback_session(self) -> None:
        session_id = self._get_selected_session_id()
        if session_id:
            self._do_show_checkpoints(session_id)

    @work(thread=True)
    def _do_show_checkpoints(self, session_id: str) -> None:
        api: APIClient = self.app.api_client  # type: ignore[attr-defined]
        try:
            checkpoints = api.list_checkpoints(session_id)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"List checkpoints failed: {exc}")
            return
        if not checkpoints:
            self.app.call_from_thread(self._show_error, "No checkpoints available.")
            return
        # Rollback to the most recent checkpoint
        latest = checkpoints[-1]
        try:
            api.rollback_checkpoint(latest["id"])
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Rollback failed: {exc}")
            return
        self._load_data()

    def action_answer_question(self) -> None:
        question = self._get_selected_question()
        if question:
            self._answering_question = question
            answer_input = self.query_one("#rescue-answer-input", Input)
            answer_input.display = True
            answer_input.value = ""
            answer_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle answer submission."""
        answer_input = self.query_one("#rescue-answer-input", Input)
        answer_input.display = False

        answer_text = event.value.strip()
        if not answer_text:
            return

        question = getattr(self, "_answering_question", None)
        if question:
            self._do_answer(question["session_id"], question["id"], answer_text)
            self._answering_question = None

    @work(thread=True)
    def _do_answer(self, session_id: str, question_id: str, answer: str) -> None:
        api: APIClient = self.app.api_client  # type: ignore[attr-defined]
        try:
            api.answer_question(session_id, question_id, answer)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Answer failed: {exc}")
            return
        self._load_data()

    def action_toggle_maintenance(self) -> None:
        current = self._health_data.get("maintenance", False)
        self._do_maintenance(not current)

    @work(thread=True)
    def _do_maintenance(self, enabled: bool) -> None:
        api: APIClient = self.app.api_client  # type: ignore[attr-defined]
        try:
            api.set_maintenance(enabled)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Maintenance toggle failed: {exc}")
            return
        self._load_data()

    def action_refresh_data(self) -> None:
        self._load_data()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_go_back(self) -> None:
        # If we're in a screen stack, pop back; otherwise quit
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()


class RescueApp(App):
    """Minimal Textual app that goes directly to the RescueScreen."""

    TITLE = "Codehive Rescue"
    SUB_TITLE = "Emergency Mode"

    def __init__(self, base_url: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.api_client = APIClient(base_url)

    def on_mount(self) -> None:
        self.push_screen(RescueScreen())
