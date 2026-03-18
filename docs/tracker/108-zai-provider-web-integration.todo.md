# Issue #108: Z.ai provider integration in web app

## Problem

Z.ai (api.z.ai) is already supported as a provider in the CLI (`--provider zai`), but there's no way to select or configure it from the web UI. Users should be able to choose Z.ai as their AI provider when creating sessions or in app settings.

## Requirements

- [ ] Provider selection in the web UI (settings page or session config)
- [ ] Support for Z.ai API key configuration
- [ ] Provider shows in session info (which provider/model is being used)
- [ ] Seamless switching between Anthropic and Z.ai providers

## Notes

- CLI already has `--provider zai` flag and `CODEHIVE_ZAI_API_KEY` / `CODEHIVE_ZAI_BASE_URL` config
- Backend Settings already has `zai_api_key` and `zai_base_url` fields
- Need web UI for provider selection and key management
