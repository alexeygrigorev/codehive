"""Import orchestration: fetch GitHub issues, upsert into internal tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Issue
from codehive.integrations.github import client as gh_client
from codehive.integrations.github.mapper import map_github_issue


@dataclass
class ImportResult:
    """Result of an import operation."""

    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


async def import_issues(
    db: AsyncSession,
    project_id,
    owner: str,
    repo: str,
    token: str,
    *,
    since: str | None = None,
    _list_issues=None,
) -> ImportResult:
    """Import GitHub issues into the internal tracker.

    Uses _list_issues for dependency injection (testing). Defaults to
    gh_client.list_issues.
    """
    list_fn = _list_issues or gh_client.list_issues
    result = ImportResult()

    gh_issues = await list_fn(owner, repo, token, since=since)

    for gh_issue in gh_issues:
        try:
            mapped = map_github_issue(gh_issue)

            # Check if already imported
            stmt = select(Issue).where(
                Issue.project_id == project_id,
                Issue.github_issue_id == mapped["github_issue_id"],
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing is not None:
                existing.title = mapped["title"]
                existing.description = mapped["description"]
                existing.status = mapped["status"]
                result.updated += 1
            else:
                issue = Issue(
                    project_id=project_id,
                    title=mapped["title"],
                    description=mapped["description"],
                    status=mapped["status"],
                    github_issue_id=mapped["github_issue_id"],
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                db.add(issue)
                result.created += 1
        except Exception as exc:
            result.errors.append(f"Issue #{gh_issue.get('number', '?')}: {exc}")

    await db.commit()
    return result
