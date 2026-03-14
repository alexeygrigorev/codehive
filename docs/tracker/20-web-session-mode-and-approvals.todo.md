# 20: Web Session Mode Switcher and Approval UI

## Description
Add the session mode indicator and switcher (Brainstorm/Interview/Planning/Execution/Review) to the session view. Also implement inline approval prompts for actions that require user confirmation.

## Scope
- `web/src/components/SessionModeIndicator.tsx` -- Display current mode with visual indicator
- `web/src/components/SessionModeSwitcher.tsx` -- UI to switch between agent modes
- `web/src/components/ApprovalPrompt.tsx` -- Inline approval/rejection UI for pending actions
- `web/src/components/ApprovalBadge.tsx` -- Notification badge for pending approvals
- `web/src/api/approvals.ts` -- API hooks for approving/rejecting actions

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #05 (session mode field in session CRUD)
- Depends on: #07 (approval.required events)
