# 36: GitHub Webhook Handler and Auto-Session Trigger

## Description
Implement a webhook endpoint that receives GitHub issue events (created, updated) and can auto-create codehive sessions for new issues. Support configurable trigger modes: manual, suggest, or auto.

## Scope
- `backend/codehive/integrations/github/webhook.py` -- Webhook receiver: validate signature, parse payload, route to handlers
- `backend/codehive/integrations/github/triggers.py` -- Auto-session trigger logic: create session from GitHub issue based on project config
- `backend/codehive/api/routes/github.py` -- Extend with webhook endpoint (`POST /api/webhooks/github`)
- `backend/tests/test_github_webhook.py` -- Webhook handling and trigger tests

## Trigger modes
- `manual` -- Import issues only, no sessions created
- `suggest` -- Import issues and notify user to create session
- `auto` -- Import issues and automatically create sessions

## Dependencies
- Depends on: #35 (GitHub issue import)
- Depends on: #05 (session CRUD for auto-creation)
