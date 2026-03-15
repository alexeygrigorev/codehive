"""Pydantic schemas for the session diffs endpoint."""

from pydantic import BaseModel


class DiffFileEntry(BaseModel):
    """A single file's diff information."""

    path: str
    diff_text: str
    additions: int
    deletions: int


class SessionDiffsResponse(BaseModel):
    """Response schema for GET /api/sessions/{session_id}/diffs."""

    session_id: str
    files: list[DiffFileEntry]
