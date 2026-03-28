"""Post pipeline progress comments on GitHub issues."""

from __future__ import annotations

import httpx

from codehive.integrations.github.client import GITHUB_API_BASE, GitHubAPIError, _headers

# Map internal pipeline step names to human-readable descriptions.
_STEP_LABELS: dict[str, str] = {
    "grooming": "grooming started",
    "implementing": "implementation started",
    "testing": "testing started",
    "accepting": "review started",
    "done": "done",
}


def build_pipeline_message(step: str, commit_sha: str | None = None) -> str:
    """Build a human-readable pipeline status message.

    Examples:
        >>> build_pipeline_message("grooming")
        '[Codehive] Pipeline: grooming started.'
        >>> build_pipeline_message("done", commit_sha="abc1234")
        '[Codehive] Pipeline: done. Commit: abc1234.'
    """
    label = _STEP_LABELS.get(step, step)
    msg = f"[Codehive] Pipeline: {label}."
    if commit_sha:
        msg = f"[Codehive] Pipeline: {label}. Commit: {commit_sha}."
    return msg


async def post_pipeline_comment(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    message: str,
) -> None:
    """POST a comment to a GitHub issue.

    Raises GitHubAPIError on non-2xx responses.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    headers = _headers(token)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=headers,
            json={"body": message},
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise GitHubAPIError(resp.status_code, resp.text)
