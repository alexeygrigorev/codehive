"""Reusable styled data table widget."""

from __future__ import annotations

from textual.widgets import DataTable as _BaseDataTable


class StyledDataTable(_BaseDataTable):
    """A thin wrapper around Textual's DataTable with project-default styles."""

    DEFAULT_CSS = """
    StyledDataTable {
        height: 1fr;
    }
    """
