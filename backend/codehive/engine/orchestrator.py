"""Orchestrator mode: restricted tool set, system prompt, and report aggregation."""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Orchestrator system prompt
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM_PROMPT: str = (
    "You are an orchestrator agent. Your role is to plan, decompose tasks, "
    "and delegate work to sub-agents. Do not edit files directly. "
    "Instead, use spawn_subagent to create sub-agents that will perform "
    "the actual coding, testing, and file modifications.\n\n"
    "You may use read_file and search_files to gather context, "
    "and run_shell for observation (e.g., running tests, checking status). "
    "Monitor sub-agent progress and aggregate their reports to decide "
    "next steps: spawn more sub-agents, fix issues by spawning a fix agent, "
    "or declare the mission complete."
)

# ---------------------------------------------------------------------------
# Allowed tools in orchestrator mode
# ---------------------------------------------------------------------------

ORCHESTRATOR_ALLOWED_TOOLS: set[str] = {
    "spawn_subagent",
    "read_file",
    "search_files",
    "run_shell",
    "get_subsession_result",
    "list_subsessions",
    "create_task",
}


def filter_tools(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only the tool definitions whose names are in ORCHESTRATOR_ALLOWED_TOOLS.

    Tools like edit_file and git_commit are excluded in orchestrator mode.
    """
    return [t for t in tool_definitions if t.get("name") in ORCHESTRATOR_ALLOWED_TOOLS]


# ---------------------------------------------------------------------------
# Report aggregation
# ---------------------------------------------------------------------------


def aggregate_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate validated sub-agent reports into a progress summary.

    Each report is expected to have keys: status, files_changed, warnings
    (as returned by SubAgentManager.collect_report).

    Returns a dict with:
    - total: number of reports
    - completed: count with status == "completed"
    - failed: count with status == "failed"
    - blocked: count with status == "blocked"
    - files_changed: deduplicated merged list of all files
    - warnings: merged list of all warnings (not deduplicated)
    - overall_status: "has_failures" if any failed, else "has_blocked" if any blocked,
      else "all_completed"
    """
    completed = 0
    failed = 0
    blocked = 0
    all_files: list[str] = []
    all_warnings: list[str] = []
    seen_files: set[str] = set()

    for report in reports:
        status = report.get("status", "")
        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        elif status == "blocked":
            blocked += 1

        for f in report.get("files_changed", []):
            if f not in seen_files:
                seen_files.add(f)
                all_files.append(f)

        all_warnings.extend(report.get("warnings", []))

    if failed > 0:
        overall_status = "has_failures"
    elif blocked > 0:
        overall_status = "has_blocked"
    else:
        overall_status = "all_completed"

    return {
        "total": len(reports),
        "completed": completed,
        "failed": failed,
        "blocked": blocked,
        "files_changed": all_files,
        "warnings": all_warnings,
        "overall_status": overall_status,
    }
