# Issue #127: Add GitHub Copilot CLI as an engine option

## Problem

GitHub Copilot has a CLI tool that can be used for coding tasks. We should support it alongside Claude Code and Codex as another CLI-based engine option.

## Requirements

- [ ] Add "copilot" as a CLI-based engine/provider
- [ ] Detect availability via `which github-copilot` or similar
- [ ] Show in provider dropdown when available
- [ ] Stream output to web chat

## Research Required (PM must do during grooming)

- [ ] What is the GitHub Copilot CLI tool called? (`gh copilot`? `github-copilot`?)
- [ ] What flags does it support for non-interactive use?
- [ ] Does it support streaming JSON output like Claude (`--output-format stream-json`)?
- [ ] Does it support session resume?
- [ ] What authentication does it use? (GitHub account, Copilot subscription)
- [ ] Can it be used as a coding agent (tool use, file edits) or just chat/suggestions?
- [ ] How does it compare to Claude Code and Codex in terms of capabilities?
- [ ] Is there an API alternative (like we have OpenAI API alongside Codex CLI)?

## Notes

- Follows the same pattern as ClaudeCodeEngine (#121) and CodexCLIEngine (#111)
- CLI detection via `shutil.which()` like other CLI providers
- No API key needed if using CLI with existing GitHub auth
