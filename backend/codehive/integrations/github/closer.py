"""Close GitHub issues and post comments via the GitHub REST API."""

from __future__ import annotations

import httpx

from codehive.integrations.github.client import GITHUB_API_BASE, GitHubAPIError, _headers


async def close_github_issue(
    owner: str,
    repo: str,
    issue_number: int,
    commit_sha: str,
    token: str,
) -> None:
    """Post a success comment and close the GitHub issue.

    Steps:
      1. POST a comment linking the commit SHA.
      2. PATCH the issue state to closed.

    Raises GitHubAPIError on any non-2xx response.
    """
    comments_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    issue_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
    headers = _headers(token)

    async with httpx.AsyncClient() as client:
        # 1. Post comment
        comment_body = f"Fixed in commit {commit_sha}. Auto-solved by codehive."
        resp = await client.post(
            comments_url,
            headers=headers,
            json={"body": comment_body},
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise GitHubAPIError(resp.status_code, resp.text)

        # 2. Close the issue
        resp = await client.patch(
            issue_url,
            headers=headers,
            json={"state": "closed"},
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise GitHubAPIError(resp.status_code, resp.text)


async def comment_failure(
    owner: str,
    repo: str,
    issue_number: int,
    error_details: str,
    token: str,
) -> None:
    """Post a failure comment on the GitHub issue without closing it.

    Raises GitHubAPIError on any non-2xx response.
    """
    comments_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    headers = _headers(token)

    body = f"Auto-solve failed: {error_details}. Issue left open for manual intervention."

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            comments_url,
            headers=headers,
            json={"body": body},
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise GitHubAPIError(resp.status_code, resp.text)
