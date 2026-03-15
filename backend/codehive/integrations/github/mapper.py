"""Map GitHub issue fields to internal Issue fields."""

from __future__ import annotations

# GitHub state -> internal status
_STATE_MAP: dict[str, str] = {
    "open": "open",
    "closed": "closed",
}

MAX_TITLE_LENGTH = 500


def map_github_issue(gh_issue: dict) -> dict:
    """Convert a GitHub issue dict to internal issue fields.

    Returns a dict with keys: title, description, status, github_issue_id.
    """
    title = gh_issue.get("title", "")
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH]

    state = gh_issue.get("state", "open")
    status = _STATE_MAP.get(state, "open")

    body: str | None = gh_issue.get("body")

    # Append labels to description
    labels = gh_issue.get("labels", [])
    label_names = [lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in labels]

    if label_names:
        label_line = f"\n\nLabels: {', '.join(label_names)}"
        if body:
            description = body + label_line
        else:
            description = label_line.lstrip("\n")
    else:
        description = body

    return {
        "title": title,
        "description": description,
        "status": status,
        "github_issue_id": gh_issue["number"],
    }
