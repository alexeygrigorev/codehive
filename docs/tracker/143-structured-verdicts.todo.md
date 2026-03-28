# 143 — Structured agent verdicts: PASS/FAIL/ACCEPT/REJECT

## Problem
Agents report results as free text. The orchestrator has to parse natural language to figure out if QA passed or PM accepted. This is fragile and the orchestrator can misinterpret results.

## Vision
Agents report structured verdicts that the app can act on programmatically:
- QA reports: `{ verdict: "PASS" | "FAIL", evidence: [...], criteria_results: [...] }`
- PM reports: `{ verdict: "ACCEPT" | "REJECT", feedback: "...", evidence: [...] }`
- The orchestrator reads the verdict field to decide routing — no parsing needed

## What this looks like
- A verdict is a special event type in the session
- Agent tools include a `submit_verdict` tool that records the structured result
- The orchestrator listens for verdict events to trigger the next pipeline step
- Verdicts are stored on the task log with full evidence

## Acceptance criteria
- [ ] Verdict event type with structured schema
- [ ] `submit_verdict` tool available to QA and PM agents
- [ ] Verdicts stored in task log
- [ ] Orchestrator can read verdicts programmatically (no text parsing)
- [ ] Evidence links (screenshot paths, test output) attached to verdicts
