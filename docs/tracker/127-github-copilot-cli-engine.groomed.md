# Issue #127: Add GitHub Copilot CLI as an engine option

## Status: DEFERRED

**Recommendation: Defer until GitHub Copilot CLI has a stable, documented programmatic interface.**

## Research Findings (PM grooming, 2026-03-19)

### What is the GitHub Copilot CLI?

The tool is invoked as `gh copilot` -- a subcommand of the GitHub CLI (`gh`). It is NOT a standalone binary. The `gh` CLI acts as a wrapper that downloads the actual Copilot CLI binary to `~/.local/share/gh/copilot/` on first use.

### Capabilities observed from `gh copilot --help`

- **Non-interactive mode:** Supports `-p "prompt"` for single-shot prompts (similar to `claude -p`)
- **Tool use:** Supports `--allow-tool 'shell(git)'` for selective tool access -- indicates agent-style tool calling
- **Platforms:** Windows, Linux, Darwin on amd64/arm64
- **Auth:** Uses existing GitHub authentication (Copilot subscription required)
- **Status:** Described as "currently in preview and subject to change"

### Critical gaps vs Claude Code and Codex CLI

| Capability | Claude Code CLI | Codex CLI | Copilot CLI |
|---|---|---|---|
| Non-interactive mode | `claude -p` | `codex exec` | `gh copilot -p` |
| Streaming JSON output | `--output-format stream-json` | `--json` (JSONL) | **Unknown / undocumented** |
| Session resume | `--resume {session_id}` | N/A (stateless) | **Unknown / undocumented** |
| File editing tools | Yes (built-in) | Yes (built-in) | Likely (has `--allow-tool`) |
| Shell execution | Yes (built-in) | Yes (built-in) | Yes (`--allow-tool 'shell(...)'`) |
| Parseable event stream | Well-documented JSON events | JSONL events | **No documented format** |
| Stability | GA | GA | **Preview, subject to change** |

### Why defer?

1. **No documented machine-readable output format.** Codehive engines rely on parsing structured JSON/JSONL event streams from CLI subprocesses. Without a documented `--json` or `--output-format` flag, we cannot reliably build a parser (CodexCLIParser/ClaudeCodeParser equivalent). Scraping human-readable stdout is fragile and not worth maintaining.

2. **Preview status means breaking changes.** The help text explicitly says "currently in preview and subject to change." Building an engine adapter against an unstable interface creates maintenance burden with no upside.

3. **No session resume.** The Claude Code engine uses `--resume` for multi-turn conversation within a Codehive session. Without this (or a documented alternative), the Copilot engine would be limited to single-shot interactions only.

4. **Cannot verify on this machine.** The Copilot CLI binary is not installed (`gh copilot -- --help` returns "Copilot CLI not installed"), so we cannot experimentally discover undocumented flags or output formats.

5. **No unique value add.** Claude Code and Codex CLI already cover the "CLI-based coding agent" use case. Copilot CLI does not offer capabilities that justify the integration effort at this time.

### What would unblock this?

- GitHub documents a structured output format (JSON/JSONL) for `gh copilot`
- GitHub moves Copilot CLI out of preview to GA
- A user specifically needs Copilot CLI integration (pull-based demand)

If any of these happen, this issue can be un-deferred and the implementation would follow the same trio pattern as Codex CLI:
- `copilot_cli_process.py` (CopilotCLIProcess)
- `copilot_cli_parser.py` (CopilotCLIParser)
- `copilot_cli_engine.py` (CopilotCLIEngine)

Detection would use `shutil.which("gh")` + subprocess check for `gh copilot -- --version`.

## Original Requirements (preserved)

- [ ] Add "copilot" as a CLI-based engine/provider
- [ ] Detect availability via `gh copilot` presence
- [ ] Show in provider dropdown when available
- [ ] Stream output to web chat

## Dependencies

- #111 (CodexCLIEngine) must be `.done.md` -- pattern to follow -- DONE
- #121 (ClaudeCodeEngine subagent integration) -- pattern to follow -- DONE

## Acceptance Criteria (for when this is un-deferred)

- [ ] `gh copilot -- --version` or equivalent returns version info (proves CLI is installed)
- [ ] Copilot CLI supports a documented JSON/JSONL output format
- [ ] CopilotCLIProcess can spawn `gh copilot` subprocess and read structured output
- [ ] CopilotCLIParser converts Copilot events to Codehive event format
- [ ] CopilotCLIEngine implements EngineAdapter protocol
- [ ] Provider detection: `copilot` appears in `/api/providers` when `gh copilot` is available
- [ ] `uv run pytest tests/ -v` passes with new Copilot engine tests
- [ ] Web UI shows Copilot as engine option in session creation when available

## Test Scenarios (for when this is un-deferred)

### Unit: CopilotCLIParser
- Parse structured output lines into Codehive events
- Handle malformed/incomplete lines gracefully
- Map Copilot tool call events to `tool.call.started` / `tool.call.finished`

### Unit: CopilotCLIProcess
- Spawn subprocess with correct flags
- Read stdout line-by-line
- Handle process crash (non-zero exit)
- Stop process cleanly (SIGTERM then SIGKILL)

### Unit: CopilotCLIEngine
- create_session initializes state
- send_message spawns process and yields events
- pause/resume set flags correctly

### Integration: Provider detection
- Copilot detected when `gh copilot` available
- Copilot not listed when `gh` missing or Copilot not installed

## Log

### [PM] 2026-03-19 Grooming
- Researched `gh copilot` capabilities via `gh copilot --help`
- Copilot CLI is NOT installed on dev machine (download required)
- CLI is in preview with no documented structured output format
- Compared against Claude Code CLI and Codex CLI capabilities
- VERDICT: DEFER -- no machine-readable output format, preview status, no unique value
- Acceptance criteria and test scenarios preserved for future un-deferral
- Original requirements preserved unchanged
