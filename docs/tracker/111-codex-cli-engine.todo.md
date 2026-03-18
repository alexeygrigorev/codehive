# Issue #111: Create CodexCLIEngine for `codex` CLI subprocess

## Background

Split from #110. After #110 cleans up the config and provider detection, the Codex provider needs an actual CLI-based engine (like ClaudeCodeEngine wraps the `claude` CLI).

## Requirements

- Create `CodexCLIEngine` in `backend/codehive/engine/codex_cli.py` that wraps the `codex` CLI subprocess
- Mirror the pattern of `ClaudeCodeEngine` / `ClaudeCodeProcess` / `ClaudeCodeParser`
- Wire it into `_build_engine()` so that engine_type="codex_cli" uses the new engine
- The existing `CodexEngine` (OpenAI SDK) remains for direct API usage

## Dependencies

- #110 must be `.done.md` first (config cleanup, provider detection)
