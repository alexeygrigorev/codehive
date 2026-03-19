# Issue #127: Add GitHub Copilot CLI as an engine option

## Problem

GitHub Copilot has a CLI tool (`gh copilot` / `copilot`) that supports coding agent tasks. Previously deferred because PM couldn't verify capabilities — now confirmed installed and fully capable.

## Confirmed CLI Capabilities

```
copilot -p "prompt" --output-format json --allow-all-tools --autopilot
copilot -p "prompt" --resume {sessionId} --output-format json --allow-all-tools
copilot --continue --output-format json --allow-all-tools
```

Key flags:
- `-p "prompt"` — non-interactive, single prompt (same as claude -p)
- `--output-format json` — JSON output (same as claude --output-format stream-json)
- `--resume [sessionId]` — resume previous session (same as claude --resume)
- `--continue` — resume most recent session
- `--allow-all-tools` — auto-approve all tools (same as codex --full-auto)
- `--autopilot` — auto-continuation in prompt mode
- `--add-dir <directory>` — set working directory

## Requirements

- [ ] Add "copilot" as a CLI-based engine/provider
- [ ] Create CopilotCLIEngine following the same pattern as ClaudeCodeEngine and CodexCLIEngine
- [ ] Detect availability via `shutil.which("copilot")` or `shutil.which("copilot")`
- [ ] Show in provider dropdown when available
- [ ] Stream JSON events from stdout to SSE for web client
- [ ] Support --resume for multi-turn sessions
- [ ] Auto-retry on crash (same pattern as ClaudeCodeEngine)

## Research Required (PM during grooming)

- [ ] What does `--output-format json` actually output? Run a test and capture the JSON structure
- [ ] Map Copilot JSON events to codehive event format (message.created, tool.call.started, etc.)
- [ ] Does it emit a session init event with session ID? (needed for --resume)
- [ ] What tool types does it support? (file read/write, shell, search)
- [ ] Test: `gh copilot -- -p "say hello" --output-format json --allow-all-tools 2>&1 | head -50`

## Notes

- Follows the trio pattern: CopilotCLIProcess, CopilotCLIParser, CopilotCLIEngine
- Same architecture as ClaudeCodeEngine (#121) and CodexCLIEngine (#111)
- No API key needed — uses GitHub auth from `gh` CLI
