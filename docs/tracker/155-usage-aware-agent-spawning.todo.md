# 155 — Usage-aware agent spawning: switch engines when limits approach

## Problem
When Claude Code or another engine hits usage limits, the orchestrator keeps trying to use it and fails. There's no automatic failover to another available engine.

## Vision
The orchestrator monitors usage and automatically switches to a different engine when limits are approaching:
- Track per-engine usage (tokens, requests, rate limits)
- When an engine reports rate limiting or high usage, mark it as "throttled"
- Spawn the next task's sub-agent on a different available engine
- Resume using the original engine when the limit window resets

## What this looks like
- Engine reports rate limit → orchestrator marks it throttled for N minutes
- Next spawn checks throttled engines and picks an alternative
- If all engines are throttled, wait and retry with backoff
- Usage dashboard shows which engines are throttled and why

## Acceptance criteria
- [ ] Orchestrator tracks per-engine throttle state
- [ ] Rate limit events from engines mark them as throttled
- [ ] Spawning logic picks non-throttled engines first
- [ ] Fallback chain: preferred engine → other available engines → wait + retry
- [ ] Throttle state expires after configurable cooldown
- [ ] Pipeline UI shows throttle status per engine
