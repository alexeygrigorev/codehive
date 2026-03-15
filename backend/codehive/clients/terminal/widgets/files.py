"""Changed files panel widget: displays file diffs with addition/deletion counts."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static


class FileRow(Static):
    """A single file row showing path, additions, and deletions."""

    DEFAULT_CSS = """
    FileRow {
        padding: 0 1;
    }
    """

    def __init__(self, path: str, additions: int, deletions: int, **kwargs: object) -> None:
        markup = f"{path}  [green]+{additions}[/green] [red]-{deletions}[/red]"
        super().__init__(markup, **kwargs)  # type: ignore[arg-type]


class _FilesEmpty(Static):
    """Placeholder for empty file changes list."""

    DEFAULT_CSS = """
    _FilesEmpty {
        padding: 1;
        color: $text-muted;
    }
    """


class FilesPanel(Vertical):
    """Panel listing changed files with addition/deletion counts."""

    DEFAULT_CSS = """
    FilesPanel {
        height: 1fr;
        border: solid $primary;
    }
    #files-title {
        padding: 0 1;
        text-style: bold;
        background: $primary-background;
    }
    #files-scroll {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Changed Files", id="files-title")
        yield VerticalScroll(
            _FilesEmpty("No changes"),
            id="files-scroll",
        )

    def load_diffs(self, diffs: list[dict[str, Any]]) -> None:
        """Replace displayed files with the given list."""
        scroll = self.query_one("#files-scroll", VerticalScroll)
        scroll.remove_children()
        if not diffs:
            scroll.mount(_FilesEmpty("No changes"))
            return
        for diff in diffs:
            scroll.mount(
                FileRow(
                    path=diff.get("path", ""),
                    additions=diff.get("additions", 0),
                    deletions=diff.get("deletions", 0),
                )
            )
