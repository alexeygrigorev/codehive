"""GitHub REST API v3 client using httpx."""

from __future__ import annotations

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """Raised on non-200 responses from the GitHub API."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API error {status_code}: {message}")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _is_pull_request(issue: dict) -> bool:
    return "pull_request" in issue


async def list_issues(
    owner: str,
    repo: str,
    token: str,
    *,
    state: str = "all",
    since: str | None = None,
) -> list[dict]:
    """Fetch issues (not PRs) from a GitHub repo, handling pagination."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
    params: dict[str, str] = {"state": state, "per_page": "100"}
    if since is not None:
        params["since"] = since

    all_issues: list[dict] = []

    async with httpx.AsyncClient() as client:
        while url is not None:
            response = await client.get(url, headers=_headers(token), params=params)
            if response.status_code != 200:
                raise GitHubAPIError(
                    response.status_code,
                    response.json().get("message", response.text),
                )

            items = response.json()
            for item in items:
                if not _is_pull_request(item):
                    all_issues.append(item)

            # Handle pagination via Link header
            url = _parse_next_link(response.headers.get("link"))
            # Only use params on the first request; subsequent URLs include params
            params = {}

    return all_issues


async def get_issue(owner: str, repo: str, number: int, token: str) -> dict:
    """Fetch a single issue by number."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{number}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=_headers(token))
        if response.status_code != 200:
            raise GitHubAPIError(
                response.status_code,
                response.json().get("message", response.text),
            )
        return response.json()


def _parse_next_link(link_header: str | None) -> str | None:
    """Parse the 'next' URL from a GitHub Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            # Extract URL between < and >
            start = part.index("<") + 1
            end = part.index(">")
            return part[start:end]
    return None
