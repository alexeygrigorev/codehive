# 23: Web Sub-Agent Tree View

## Description
Build the sub-agent tree view UI component in the web app. Displays the parent-child hierarchy of sessions with per-agent status, and allows clicking into any sub-agent to view its full session. Includes aggregated progress display in the orchestrator view.

## Scope
- `web/src/components/sidebar/SubAgentPanel.tsx` -- Replace placeholder with real tree view
- `web/src/components/SubAgentTree.tsx` -- Recursive tree component showing session hierarchy
- `web/src/components/SubAgentNode.tsx` -- Individual sub-agent node with status indicator
- `web/src/components/AggregatedProgress.tsx` -- Progress bar aggregating all sub-agent statuses
- `web/src/api/subagents.ts` -- API hooks for sub-agent tree data

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #21 (sub-agent spawning backend)
- Depends on: #17 (session sidebar where tree view lives)
