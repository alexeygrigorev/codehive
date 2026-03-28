# 159 -- E2E tests for archive/delete projects and sessions

## Problem

Issue #156 implemented archive/delete for projects and sessions with full backend and frontend unit/integration test coverage (39 tests). However, the 4 E2E Playwright test scenarios specified in the acceptance criteria were not implemented. The project has existing Playwright infrastructure under `web/e2e/`.

## Dependencies

- #156 (archive/delete projects and sessions) -- done

## Acceptance Criteria

- [ ] `web/e2e/archive-delete.spec.ts` exists with 4+ E2E tests
- [ ] E2E: Archive a project, verify it disappears from sidebar and dashboard
- [ ] E2E: View archived projects page, restore one, verify it reappears in sidebar
- [ ] E2E: Delete a session, verify it disappears from session list
- [ ] E2E: Attempt to delete project with sessions via API, verify cascade succeeds
- [ ] All existing E2E tests still pass

## Test Scenarios

### E2E: Archive project flow
- Precondition: project "test-archive" exists with 1 session
- Steps: navigate to project page, click Archive, confirm
- Assertions: project gone from sidebar, gone from dashboard, visible on archived page

### E2E: Restore archived project
- Precondition: archived project "test-restore" exists
- Steps: navigate to /projects/archived, click Restore, confirm
- Assertions: project gone from archived page, visible in sidebar

### E2E: Delete session
- Precondition: project with 2 sessions exists
- Steps: navigate to project page, click delete on one session, confirm
- Assertions: session gone from list, other session still visible

### E2E: Cascade delete via API
- Precondition: project with sessions exists
- Steps: DELETE /api/projects/{id}
- Assertions: project gone, sessions gone
