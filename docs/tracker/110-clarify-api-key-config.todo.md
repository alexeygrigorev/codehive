# Issue #110: Clarify API key configuration and update README

## Problem

Currently Z.ai is configured by setting `CODEHIVE_ANTHROPIC_API_KEY` with the Z.ai key and `CODEHIVE_ZAI_BASE_URL` with the Z.ai endpoint. This is confusing because:

1. The Anthropic key field is being reused for a non-Anthropic provider
2. There's a separate `CODEHIVE_ZAI_API_KEY` field that should be the canonical place for Z.ai keys
3. It's unclear to users which env vars to set for which providers
4. The README doesn't document the API key configuration

## Provider Model

Codehive supports three providers. Each has its own config. If a key is not set, that provider is **unavailable** (hidden from the UI, returns error if selected).

| Provider | How it works | Env vars |
|----------|-------------|----------|
| Claude (Anthropic) | Via the `claude` CLI command (Claude Code). No API key needed — uses the user's existing Claude Code authentication. | None — always available if `claude` is installed |
| Z.ai | API key + base URL | `CODEHIVE_ZAI_API_KEY`, `CODEHIVE_ZAI_BASE_URL` |
| OpenAI (Codex) | API key | `CODEHIVE_OPENAI_API_KEY` |

## Requirements

- [ ] Remove `CODEHIVE_ANTHROPIC_API_KEY` — Claude works via the `claude` command, not an API key
- [ ] Z.ai uses only `CODEHIVE_ZAI_API_KEY` (not the Anthropic key field)
- [ ] OpenAI uses `CODEHIVE_OPENAI_API_KEY`
- [ ] If a provider's key is not set, it is unavailable:
  - Not shown in provider dropdown (or shown as disabled/grayed out)
  - Returns clear error if somehow selected
- [ ] Claude/native engine should always be available (it uses `claude` CLI, no key needed)
- [ ] Update the providers endpoint to reflect availability based on key presence
- [ ] Update README with clear "Configuration" section:
  - Provider table (above)
  - Example .env file with only the keys the user needs
  - How to verify: `curl /api/providers` shows which are available
- [ ] Create `.env.example` with all supported env vars documented

## Architecture Decision

The native engine delegates to the `claude` CLI — it does NOT call the Anthropic API directly. Claude Code handles its own authentication. This means:

- `CODEHIVE_ANTHROPIC_API_KEY` should be **removed entirely** from the config
- The native engine invokes `claude` as a subprocess
- No API key configuration needed for Claude — it's always available if `claude` is installed
- The NativeEngine class needs to be refactored from direct Anthropic SDK calls to `claude` CLI invocation
