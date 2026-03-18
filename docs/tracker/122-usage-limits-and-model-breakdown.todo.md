# Issue #122: Show Claude Code & Codex usage limits with per-model breakdown

## Problem

The current usage tracking (#107) only tracks token counts per API call from our own engines. But the user also needs to see their **plan usage limits** — the same data shown in Claude Code's `/usage` command:

```
Plan usage limits
Current session: 21% used (resets in 2h 58m)
Weekly limits: 91% used (resets Fri 10:00 AM)
Sonnet only: 0% used
```

This is about **limits** (how much of your plan you've consumed) not just raw token counts.

## Requirements

- [ ] Show Claude Code plan usage limits (session %, weekly %, per-model %)
- [ ] Show Codex usage/limits if available
- [ ] Per-model breakdown (e.g., Opus vs Sonnet usage)
- [ ] Reset timers (when limits reset)
- [ ] Integrate into the existing Usage page

## Research Required (PM must do during grooming)

- [ ] How does Claude Code expose usage limits?
  - Check `claude` CLI: is there a `--usage` flag or API?
  - Check if `claude` outputs usage info in stream-json events
  - Check if there's a local file/cache with usage data
  - Research Claude Code SDK / API for programmatic access to limits
- [ ] How does Codex expose usage limits?
  - Check `codex` CLI for usage commands
  - Check OpenAI API for usage/billing endpoints
- [ ] What data format do these limits come in?
- [ ] Can we poll for updated limits periodically?

## UI Design

Should look similar to what Claude Code shows:
- Progress bars for each limit tier (session, weekly, per-model)
- Reset countdown timers
- Per-model breakdown section
- Integrated into the Usage page alongside our own token tracking

## Notes

- This is different from #107 (which tracks our own API call tokens)
- This is about the upstream provider's rate limits on the user's plan
- Claude Code limits are tied to the user's Anthropic plan (Pro, Team, etc.)
- The data source is the CLI tool itself, not our backend
