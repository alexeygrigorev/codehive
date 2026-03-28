# 144 -- Git commit automation: backend commits after PM accepts

## Problem

After PM accepts a task, someone needs to commit the code. Currently the orchestrator transitions the task to `done` via `pipeline_transition` but performs no git operations. The commit must be done manually by the user or by an external Claude Code orchestrator session.

## Vision

The backend provides a `GitService` that can perform git operations (status, stage, commit, push) on a project's local directory. When the orchestrator transitions a task to `done`, it calls the git service to stage changed files, create a commit with a conventional message, and optionally push to the remote.

## Dependencies

- Issue #03 (database models) -- DONE
- Issue #04 (project CRUD) -- DONE
- Issue #08 (execution layer) -- DONE

No blocking dependencies. The `Project.path` field and `orchestrator_service.py` already exist.

## User Stories

### Story: Orchestrator auto-commits after PM accepts a task

1. A task is in `accepting` pipeline status
2. PM agent returns VERDICT: ACCEPT
3. The orchestrator calls `route_result("accepting", Verdict.ACCEPT)` which returns `"done"`
4. Before (or immediately after) transitioning to `done`, the orchestrator calls `GitService.commit_task(project, task)`
5. The git service checks `project.path` is a valid git repository
6. The git service runs `git add -A` in the project directory
7. The git service runs `git commit -m "Implement task #N: <task title>"`
8. The commit SHA is logged to the task's issue log
9. If the project has `git_auto_push` enabled in `github_config`, the service also runs `git push`

### Story: Git commit fails gracefully when project has no path

1. A project has `path = None` (no local directory configured)
2. PM accepts a task for this project
3. The orchestrator attempts to call the git service
4. The git service raises `GitError` with a clear message: "Project has no local path configured"
5. The orchestrator logs the error but does NOT block the transition to `done`
6. The task still moves to `done` -- the commit failure is non-fatal

### Story: Git commit fails gracefully on dirty index conflicts

1. A project directory has unrelated uncommitted changes from another process
2. PM accepts a task
3. The git service attempts to commit
4. If git returns a non-zero exit code, the service raises `GitError` with stderr
5. The orchestrator logs the error to the issue log
6. The task still moves to `done` -- again, non-fatal

## Acceptance Criteria

- [ ] `GitService` class exists at `backend/codehive/core/git_service.py`
- [ ] `GitService.repo_status(path)` returns current branch, dirty file count, and last commit SHA
- [ ] `GitService.stage_all(path)` runs `git add -A` in the given directory
- [ ] `GitService.commit(path, message)` runs `git commit -m <message>` and returns the commit SHA
- [ ] `GitService.push(path)` runs `git push` and returns success/failure
- [ ] `GitService.commit_task(project, task)` is the high-level method: stages, commits with conventional message `"Implement task #N: <title>"`, optionally pushes
- [ ] All git subprocess calls use `asyncio.subprocess` (async) or `asyncio.to_thread(subprocess.run, ...)` -- never blocking the event loop
- [ ] `GitError` exception class for all git failures, with exit code and stderr
- [ ] Orchestrator calls `GitService.commit_task` when a task transitions to `done` (after PM accepts)
- [ ] Git failures are logged but do NOT prevent the task from reaching `done` status
- [ ] Push only happens when `project.github_config` contains `"auto_push": true`
- [ ] `uv run pytest tests/ -v` passes with 8+ new tests
- [ ] `uv run ruff check` is clean

## Technical Notes

### File placement

- New file: `backend/codehive/core/git_service.py` -- contains `GitService` and `GitError`
- Modified: `backend/codehive/core/orchestrator_service.py` -- hook git commit into the `_run_task_pipeline` method when `target == "done"`
- New file: `backend/tests/test_git_service.py`

### GitService design

Follow the pattern from `backup.py`: use `subprocess.run` with `capture_output=True` and `check=False`, then inspect return code. Wrap in `asyncio.to_thread` for async compatibility.

```python
class GitError(Exception):
    def __init__(self, message: str, exit_code: int = 1, stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr

class GitService:
    @staticmethod
    async def repo_status(path: str) -> dict:
        """Return branch, dirty count, last SHA."""

    @staticmethod
    async def stage_all(path: str) -> None:
        """git add -A"""

    @staticmethod
    async def commit(path: str, message: str) -> str:
        """git commit, returns SHA"""

    @staticmethod
    async def push(path: str) -> None:
        """git push"""

    @staticmethod
    async def commit_task(project: Project, task: Task) -> str | None:
        """High-level: stage + commit + optional push. Returns SHA or None on failure."""
```

### Orchestrator integration point

In `_run_task_pipeline`, after the `pipeline_transition(db, task_id, "done", ...)` call, add:

```python
if target == "done":
    try:
        sha = await GitService.commit_task(project, task)
        # log sha to issue
    except GitError as e:
        logger.warning("Git commit failed for task %s: %s", task_id, e)
        # log failure to issue -- non-fatal
```

### Push configuration

Use the existing `project.github_config` JSON field. Check for `{"auto_push": true}`. No schema migration needed -- `github_config` is already a nullable JSON column.

### Testing strategy

All tests must use a real temporary git repo (via `tmp_path` fixture) -- NOT mock subprocess calls. This ensures the git commands actually work.

## Test Scenarios

### Unit: GitService low-level operations
- `repo_status` on a valid git repo returns branch name, 0 dirty files, and a SHA
- `repo_status` on a non-git directory raises `GitError`
- `stage_all` stages new and modified files
- `commit` with staged changes returns a valid SHA (40 hex chars)
- `commit` with no staged changes raises `GitError` (nothing to commit)
- `push` on a repo with no remote raises `GitError`

### Unit: GitService.commit_task high-level
- `commit_task` with a valid project+task creates a commit with message `"Implement task #<N>: <title>"`
- `commit_task` with `project.path = None` raises `GitError`
- `commit_task` with `auto_push=True` in github_config attempts push (can mock the remote or expect GitError for no remote)
- `commit_task` with `auto_push` absent or false does NOT attempt push

### Unit: Orchestrator git integration
- When orchestrator transitions a task to `done`, `GitService.commit_task` is called (use mock/monkeypatch)
- When `GitService.commit_task` raises `GitError`, the task still reaches `done` status
- The commit SHA is logged to the issue log on success
- The error message is logged to the issue log on failure

### Integration: End-to-end with temp git repo
- Create a temp git repo, add a file, create a Project pointing to it, create a Task
- Call `GitService.commit_task` and verify: commit exists in git log, message matches convention

## Log

### [SWE] 2026-03-28 12:00
- Created `GitService` class with `GitError` exception at `backend/codehive/core/git_service.py`
- Implemented all required static methods: `repo_status`, `stage_all`, `commit`, `push`, `commit_task`
- All subprocess calls wrapped in `asyncio.to_thread(_run_git, ...)` following backup.py pattern
- `commit_task` builds conventional message `"Implement task #N: <title>"`, checks `github_config["auto_push"]`
- Integrated into `orchestrator_service.py`: added `_try_git_commit` method called after `pipeline_transition` to `done`
- Git failures are non-fatal: caught as `GitError`, logged to issue log, task still reaches done
- On success, commit SHA is logged to issue log
- Files modified: `backend/codehive/core/git_service.py` (new), `backend/codehive/core/orchestrator_service.py`, `backend/tests/test_git_service.py` (new)
- Tests added: 16 tests covering all acceptance criteria
  - repo_status: valid repo, non-git directory
  - stage_all: stages new and modified files
  - commit: returns SHA, nothing-to-commit raises GitError
  - push: no remote raises GitError
  - commit_task: conventional message, no path raises, auto_push true/false/absent
  - Orchestrator integration: done calls git_commit, failure non-fatal, SHA logged, error logged
  - E2E: real temp repo end-to-end flow
- Build results: 16 new tests pass, 44 existing orchestrator tests pass (60 total), ruff clean
- Known limitations: none

### [QA] 2026-03-28 12:30
- Tests: 16/16 passed in test_git_service.py (0.78s)
- Full suite: 2310 passed, 3 skipped, 0 failed (222s)
- Ruff check: clean on all changed files (git_service.py, orchestrator_service.py, test_git_service.py)
- Ruff format: clean on all changed files
- Note: pre-existing ruff issues in test_verdicts.py/verdicts.py (unrelated to this issue)
- Acceptance criteria:
  1. GitService class at core/git_service.py: PASS
  2. repo_status returns branch/dirty_count/last_sha: PASS
  3. stage_all runs git add -A: PASS
  4. commit runs git commit -m, returns SHA: PASS
  5. push runs git push: PASS
  6. commit_task high-level with conventional message "Implement task #N: title": PASS
  7. All subprocess calls via asyncio.to_thread: PASS
  8. GitError exception with exit_code and stderr: PASS
  9. Orchestrator calls commit_task on transition to done: PASS
  10. Git failures non-fatal (task still reaches done): PASS
  11. Push gated on github_config["auto_push"]: PASS
  12. 8+ new tests (16 total): PASS
  13. ruff check clean: PASS
- Tests use real temp git repos (tmp_path fixture) for unit and e2e tests: PASS
- VERDICT: PASS

### [PM] 2026-03-28 13:00
- Reviewed diff: 3 files changed (git_service.py new, orchestrator_service.py modified, test_git_service.py new)
- Results verified: real data present -- QA ran 16/16 tests passing, 2310 total suite passing, ruff clean
- Acceptance criteria: all 13 met
  1. GitService class at core/git_service.py: MET
  2. repo_status returns branch/dirty_count/last_sha: MET
  3. stage_all runs git add -A: MET
  4. commit returns SHA: MET
  5. push runs git push: MET
  6. commit_task with conventional message "Implement task #N: title": MET
  7. All subprocess calls via asyncio.to_thread: MET
  8. GitError with exit_code and stderr: MET
  9. Orchestrator calls commit_task on done transition: MET
  10. Git failures non-fatal (task still reaches done): MET
  11. Push gated on github_config["auto_push"]: MET
  12. 8+ new tests (16 actual): MET
  13. ruff check clean: MET
- Tests are meaningful: real temp git repos via tmp_path, verify actual git log output, orchestrator integration tests check call, non-fatal failure, SHA logging, error logging
- Follow-up issues created: none needed
- VERDICT: ACCEPT
