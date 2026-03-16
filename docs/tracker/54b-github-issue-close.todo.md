# 54b: GitHub Auto-Solve -- Issue Close and Error Handling

## Description
After the solver completes (54a), close the GitHub issue via the API with a comment linking the commit SHA. On failure, add a comment with error details and leave the issue open.

## Implementation Plan

### 1. GitHub issue close
- `backend/codehive/integrations/github/closer.py`
- `async def close_github_issue(project_id, github_issue_number, commit_sha)`
  - Use existing `github/client.py` httpx client
  - POST comment: "Fixed in commit {sha}. Auto-solved by codehive."
  - PATCH issue state to "closed"

### 2. Error comment
- `async def comment_failure(project_id, github_issue_number, error_details)`
  - POST comment: "Auto-solve failed: {error_details}. Issue left open for manual intervention."
  - Do NOT close the issue

### 3. Integration with solver
- In `solver.py`, after successful push, call `close_github_issue()`
- After failure, call `comment_failure()`
- Both calls use the project's `github_config` for repo owner/name and token

### 4. Update internal issue status
- On success: update codehive issue status to "closed"
- On failure: update codehive issue status to "open" with failure metadata

## Acceptance Criteria

- [ ] On successful solve, GitHub issue is closed via API
- [ ] Closing comment includes the commit SHA
- [ ] On failure, a comment is posted with error details
- [ ] On failure, the GitHub issue remains open
- [ ] Internal codehive issue status is updated accordingly
- [ ] `uv run pytest tests/test_closer.py -v` passes with 4+ tests

## Test Scenarios

### Unit: close_github_issue
- Mock httpx, call close function, verify PATCH to issues endpoint with state=closed
- Verify comment POST includes commit SHA

### Unit: comment_failure
- Mock httpx, call failure function, verify comment POST includes error details
- Verify issue is NOT patched to closed

### Integration: Solver to closer
- Mock solver success, verify close_github_issue is called
- Mock solver failure, verify comment_failure is called

## Dependencies
- Depends on: #54a (solver orchestration), #35 (GitHub client)
