# 139 — Orchestrator auto-pipeline: rigid, self-sustaining task execution

## Problem
The orchestrator (currently the Claude Code session) sometimes stops, asks "shall we proceed?", skips steps, or ignores the process. The pipeline relies on the LLM remembering to follow PROCESS.md.

## Vision
The orchestrator is a backend service that rigidly executes the pipeline:
1. Picks tasks from the backlog (2 at a time)
2. For each task, spawns the correct agent for the current pipeline step
3. When an agent finishes, automatically moves to the next step
4. On rejection, automatically routes back with feedback
5. On acceptance, commits and pulls next batch
6. Never stops, never asks, never skips

## What this looks like
- `POST /api/orchestrator/start` — starts the pipeline loop for a project
- `POST /api/orchestrator/add-task` — adds a task to the pool (orchestrator picks it up)
- The orchestrator is a background worker that:
  - Polls for tasks in `backlog` status
  - Picks 2, spawns PM grooming sessions
  - When grooming done → spawns SWE sessions
  - When SWE done → spawns QA sessions
  - When QA pass → spawns PM accept sessions
  - When QA fail → spawns SWE with feedback
  - When PM accept → commits, moves to done
  - When PM reject → spawns SWE with feedback
  - Pulls next 2 when batch is done
- Web UI shows the pipeline widget: which tasks are in which stage, which agents are active

## Acceptance criteria
- [ ] Orchestrator runs as a background service
- [ ] Automatically picks tasks and spawns correct agents
- [ ] Follows state machine — cannot skip steps
- [ ] Rejection loops work (QA fail → SWE → QA, PM reject → SWE → QA → PM)
- [ ] Auto-pulls next batch when current batch completes
- [ ] Web UI shows live pipeline status
- [ ] Never blocks waiting for user input
