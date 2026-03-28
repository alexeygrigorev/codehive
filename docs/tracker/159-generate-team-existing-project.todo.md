# 159 — Generate team for existing projects

## Problem
Teams are only auto-generated when creating a new project. Existing projects that were created before the team feature (#151) have no team. There's no way to generate a default team for them from the UI.

## Expected behavior
- On the project page's Team tab, if the team is empty, show a "Generate Team" button
- Clicking it creates the default team (1 PM, 2 SWE, 2 QA, 1 OnCall) just like new project creation does
- The button is only shown when the team is empty
- The user can also manually add individual team members via the existing CRUD API

## Acceptance criteria
- [ ] Backend: POST /api/projects/{id}/team/generate endpoint that calls generate_default_team
- [ ] Endpoint is idempotent — if team already exists, returns 409 or the existing team
- [ ] Frontend: "Generate Team" button shown on Team tab when team is empty
- [ ] After clicking, the team appears immediately (no page reload needed)
- [ ] Button hidden when team already has members
- [ ] Works for projects created before #151
