# 165 — Deterministic task execution: state machine drives agents, not LLM

## Problem
Currently the orchestrator is either:
1. A backend service (#139) that runs autonomously but can't be triggered interactively
2. An LLM agent that sometimes forgets the process, skips steps, or stops

We need a middle ground: the user says "solve task #10" in a session, and a **deterministic state machine** takes over. The state machine spawns agents for each step, reads their verdicts, and routes to the next step — no LLM in the control loop.

## Vision

### User interaction
```
User: "solve task #10"
System: Creates a task execution subsession for task #10
        State machine takes over:
        1. grooming → spawns PM agent, waits for completion
        2. groomed → spawns SWE agent, waits for completion
        3. implementing → spawns QA agent, waits for verdict
        4. If FAIL → back to implementing (spawns SWE with feedback)
        5. If PASS → spawns PM for acceptance
        6. If REJECT → back to implementing
        7. If ACCEPT → done, commits
```

### Key principle: code drives the process, agents do the work
- The state machine is **code** (Python), not an LLM prompt
- Each step spawns exactly one agent with a clear role and instructions
- The agent's output is parsed for a structured verdict (#143)
- The state machine reads the verdict and decides the next step
- No ambiguity, no "should I continue?", no skipped steps

### What the state machine controls
- Which agent role to spawn for each state
- What instructions to give them (task details, acceptance criteria, feedback from rejections)
- When to transition states (based on verdict events)
- When to retry (rejection loops with max attempts)
- When to commit (after PM accepts)
- When to flag for human review (max rejections exceeded)

### What agents control
- How to do the actual work (write code, run tests, review)
- What verdict to give (PASS/FAIL/ACCEPT/REJECT with evidence)
- What feedback to provide on rejection

## Architecture

```
User session (chat)
  └── "solve task #10"
        └── TaskExecutionRunner (state machine)
              ├── State: grooming
              │     └── spawn PM session → wait → read verdict
              ├── State: implementing
              │     └── spawn SWE session → wait → read verdict
              ├── State: testing
              │     └── spawn QA session → wait → read verdict
              │           ├── PASS → accepting
              │           └── FAIL → implementing (with feedback)
              ├── State: accepting
              │     └── spawn PM session → wait → read verdict
              │           ├── ACCEPT → done
              │           └── REJECT → implementing (with feedback)
              └── State: done
                    └── git commit, update tracker, notify user
```

### Corner cases to handle
- Agent crashes or times out → retry once, then flag for human
- Agent gives no verdict → parse output for implicit verdict, or flag
- Max rejections (3) → flag task, move to next
- User cancels mid-execution → gracefully stop, mark task as interrupted
- Multiple tasks running in parallel → each gets its own runner
- Agent produces partial work before crashing → preserve what was done

## Relationship to existing code
- **#139 OrchestratorService** already has most of this logic (`_run_task_pipeline`, `parse_verdict`, `route_result`, `build_instructions`). This issue refactors it into a cleaner, more reusable `TaskExecutionRunner` that can be triggered from a chat session.
- **#136 pipeline state machine** provides the valid transitions
- **#143 structured verdicts** provides the verdict parsing
- **#142 agent-task binding** links sessions to tasks
- **#144 git commit automation** handles the commit step

## Acceptance criteria
- [ ] `TaskExecutionRunner` class: takes a task ID, drives it through the full pipeline
- [ ] Each state spawns exactly one agent session with the correct role
- [ ] Transitions are deterministic: based on verdict, not LLM interpretation
- [ ] Rejection loops work with feedback propagation
- [ ] Max rejection safeguard (configurable, default 3)
- [ ] Crash/timeout handling with retry
- [ ] User can trigger via chat ("solve task #10") or API
- [ ] Progress visible in real-time (task tracker updates, log entries)
- [ ] Multiple tasks can run in parallel (each with own runner)
- [ ] Can be stopped/cancelled gracefully
- [ ] All existing OrchestratorService tests adapted or preserved
