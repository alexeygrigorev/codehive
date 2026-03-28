# 141 — GitHub issue sync: import issues into the task pool

## Problem
The article mentions: "when I create an issue in GitHub, Codehive adds it to the task pool." Currently there's no connection between GitHub issues and the Codehive task pool.

## Vision
- When a GitHub issue is created (or labeled), it appears in Codehive's task pool
- The orchestrator picks it up and runs it through the pipeline
- Status updates in Codehive are reflected back to GitHub (comments, labels)

## Acceptance criteria
- [ ] Webhook endpoint for GitHub issue events
- [ ] New GitHub issues create tasks in the Codehive backlog
- [ ] Pipeline progress posted as GitHub comments
- [ ] Task completion closes the GitHub issue
- [ ] Configurable per-project (which repo, which labels to sync)
