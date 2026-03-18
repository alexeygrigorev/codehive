# Issue #121: Use Claude Code as subagent for web sessions

## Problem

The current ClaudeCodeEngine tries to maintain interactive sessions with the `claude` CLI but it doesn't work properly. The session model is wrong — trying to keep a long-running process doesn't fit how `claude` works.

## Approach

Use Claude Code as a **subagent** — fire a task, get the result. No interactive session state needed. The telegram-writing-assistant project at `~/git/telegram-writing-assistant` shows how to do this successfully.

## Research Required (PM must do during grooming)

- [ ] Study `~/git/telegram-writing-assistant` — how it invokes Claude Code as a subagent
- [ ] How it sends prompts and gets responses
- [ ] How it handles streaming output
- [ ] How sessions/context are managed (or not)
- [ ] Research online: how other projects integrate Claude Code programmatically
- [ ] Research: `claude --print`, `claude -p`, streaming JSON output flags
- [ ] Determine the right session model for web: fire-and-forget subagent vs interactive process

## Requirements

- [ ] Claude Code works as a subagent: send a task, get streaming output back
- [ ] Web chat can send a message and see Claude Code's response streamed
- [ ] No need for long-running process management
- [ ] Works with the user's existing Claude Code authentication (no API key needed)
- [ ] Context/history management: how to pass conversation context to each subagent call

## Research Notes (from exploration)

### telegram-writing-assistant pattern (reference implementation):
- Uses `claude -p "{prompt}" --allowedTools "{tools}" --output-format stream-json --verbose`
- For resuming: `claude -p "{continuation}" --resume {session_id} ...`
- Fire-and-forget: one subprocess per task, NOT long-running
- Captures `session_id` from `system.init` event, saves to file
- `SessionRetrier` auto-resumes crashed sessions up to 3 times
- `ClaudeProgressFormatter` parses tool use events for display
- Key files: `claude_runner.py`, `session_retrier.py`, `progress_tracker.py`

### Current Codehive ClaudeCodeEngine problems:
- Uses long-running process with stdin/stdout pipes (`--input-format stream-json`)
- No `--resume` support — if process crashes, session is lost
- `_build_engine()` doesn't call `create_session()` — send_message fails
- Process model doesn't match how `claude` CLI actually works best

### Recommended approach:
- Follow telegram-writing-assistant: fire-and-forget subagent per message
- `claude -p "{message}" --output-format stream-json --resume {session_id}`
- Save session_id from first run, use `--resume` for subsequent messages
- Auto-retry on crash with SessionRetrier pattern
- Stream JSON events from stdout to SSE for the web client

### Claude CLI flags:
- `-p "prompt"` — non-interactive, single prompt
- `--output-format stream-json` — JSONL events on stdout
- `--resume SESSION_ID` — continue a previous session
- `--allowedTools "Read,Edit,Bash,Write"` — restrict tools
- `--verbose` — include tool details in output

## Notes

- This replaces/refactors the current ClaudeCodeEngine
- The telegram-writing-assistant is the reference implementation — follow its patterns
- Claude Code handles its own tool approval, context management, etc.
