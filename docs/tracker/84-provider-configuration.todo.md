# Issue #84: LLM provider configuration

## Problem

Currently the model is hardcoded to `claude-sonnet-4-20250514` and only Anthropic-compatible APIs are supported via a single API key + base URL. The user needs to:
- Configure multiple providers (Anthropic, Z.ai, OpenRouter, etc.)
- Select from available models per provider
- Switch models easily from the CLI and UI

Z.ai (api.z.ai) is the primary alternative provider, offering GLM models via an Anthropic-compatible endpoint.

## Requirements

### Provider config model
- [ ] Define a `Provider` config structure: name, base_url, api_key, available models, default model
- [ ] Store provider configs in a YAML/TOML file (e.g., `~/.codehive/providers.yml`) or in the database
- [ ] Ship sensible defaults for Anthropic and Z.ai
- [ ] Support Anthropic-compatible APIs (same SDK, different base_url + models)

### Available models

**Anthropic (default)**:
- claude-sonnet-4-20250514
- claude-haiku-4-5-20251001
- claude-opus-4-20250515

**Z.ai (api.z.ai/api/anthropic)**:
- glm-5
- glm-5-turbo
- glm-4.7
- glm-4.7-flash
- glm-4.5-air

### CLI integration
- [ ] `codehive code --model glm-4.7` — override model for a session
- [ ] `codehive code --provider zetai` — use a named provider config
- [ ] `codehive providers list` — list configured providers and their models
- [ ] `codehive providers add` — add a new provider interactively

### Engine integration
- [ ] NativeEngine accepts provider config (base_url, api_key, model) at construction
- [ ] Session creation in the API accepts optional provider/model override
- [ ] Settings fallback chain: CLI flag > session config > project config > global default

### Backend API sessions route
- [ ] Fix `_build_engine` in sessions.py to use `anthropic_base_url` from settings (currently ignored)

## Notes

- Z.ai uses Anthropic-compatible endpoints so the same `AsyncAnthropic` client works — just different base_url and model names
- Future: OpenAI-compatible providers would need a different client (out of scope for now)
- Keep it simple — a flat config file, no provider plugin system
