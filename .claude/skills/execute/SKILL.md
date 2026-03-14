---
name: execute
description: Run the full development pipeline - groom, implement, test, accept, commit, repeat
disable-model-invocation: true
---

# Execute Development Pipeline

Run the full development pipeline for codehive.

**Argument:** `[number-of-issues]` — how many issues per batch (default: 2)

Before starting, read `docs/PROCESS.md` for the full workflow.

## Steps

### 1. PM Grooming (parallel, in background)
Find all `.todo.md` files in `docs/tracker/`. For each, launch the **product-manager** agent in grooming mode. This can run in background while other work proceeds.

### 2. Pick Issues
List `.groomed.md` files in `docs/tracker/`. Pick the lowest-numbered `$1` issues (default 2). Check dependencies — skip if deps aren't in `docs/tracker/done/`. Skip issues with `[BLOCKED]` in title.

### 3. Create Task Panel
For each picked issue, create task panel items with dependencies:

```
[PM groom #N] -> [SWE #N] -> [QA #N] -> [PM accept #N] --\
                                                           +--> [Pull next]
[PM groom #M] -> [SWE #M] -> [QA #M] -> [PM accept #M] --/
```

Set blockedBy dependencies between tasks. Mark `in_progress` when starting, `completed` when done.

### 4. Implement (parallel)
For each issue, launch **software-engineer** agent with the `.groomed.md` filename. One agent per issue — never combine.

### 5. QA (parallel)
After engineer reports done, launch **tester** agent with the `.in-progress.md` filename. One agent per issue.

### 6. Handle QA Results
- **PASS**: proceed to PM review
- **FAIL**: relay tester feedback to a new **software-engineer** agent. SWE fixes, then launch **tester** again. Max 2 retries. If still failing, report to user.

### 7. PM Acceptance Review (parallel)
Launch **product-manager** agent in acceptance mode for each passing issue. One agent per issue.

### 8. Handle PM Results
- **ACCEPT**: proceed to commit
- **REJECT**: relay PM feedback to a new **software-engineer** agent. SWE fixes, **tester** re-verifies, **product-manager** re-reviews. Max 2 retries.

### 9. Commit
For each accepted issue:
1. `mv docs/tracker/NN-name.in-progress.md docs/tracker/done/NN-name.done.md`
2. `git add .`
3. `git commit -m "Implement issue NN: short description"`

### 10. Pipeline Check
After pushing, launch **oncall-engineer** to verify CI/CD is green.

### 11. Repeat
Go back to step 2. Pick next batch. Continue until no more `.groomed.md` or `.todo.md` issues remain.

**IMPORTANT:** The orchestrator NEVER writes code. It only launches agents, routes feedback, manages task panel items, and commits after PM accepts.
