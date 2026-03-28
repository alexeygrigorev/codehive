# 149 — Model selection dropdown with correct defaults per provider

## Problem
The New Session dialog has a free-form text input for model selection. The default models are wrong (e.g., "codex-mini-latest" for OpenAI, "glm-4.7" for Z.ai). Users don't know which model IDs to type.

## Expected behavior
- Dropdown list of common models per provider (populated from backend)
- Correct, up-to-date model IDs for each provider
- Option to type a custom model ID (combobox pattern — select from list OR type freely)
- Backend returns available models per provider, not just a single default

## Model data (researched March 2026)

### Claude (Anthropic)
| Model ID | Display Name | Default |
|---|---|---|
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | Yes |
| `claude-opus-4-6` | Claude Opus 4.6 | |
| `claude-sonnet-4-5` | Claude Sonnet 4.5 | |
| `claude-haiku-4-5` | Claude Haiku 4.5 | |

### OpenAI
| Model ID | Display Name | Default |
|---|---|---|
| `gpt-5.4` | GPT-5.4 | Yes |
| `gpt-5.4-mini` | GPT-5.4 Mini | |
| `o4-mini` | O4 Mini | |
| `o3` | O3 | |

### Codex CLI
| Model ID | Display Name | Default |
|---|---|---|
| `gpt-5.4` | GPT-5.4 | Yes |
| `gpt-5.3-codex` | GPT-5.3 Codex | |
| `gpt-5.4-mini` | GPT-5.4 Mini | |

### Gemini
| Model ID | Display Name | Default |
|---|---|---|
| `gemini-2.5-flash` | Gemini 2.5 Flash | Yes |
| `gemini-2.5-pro` | Gemini 2.5 Pro | |
| `gemini-3.1-pro-preview` | Gemini 3.1 Pro (Preview) | |

### Copilot CLI
| Model ID | Display Name | Default |
|---|---|---|
| `default` | Default | Yes |

### Z.ai
| Model ID | Display Name | Default |
|---|---|---|
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | Yes |
| `claude-opus-4-6` | Claude Opus 4.6 | |

## Acceptance criteria
- [ ] Backend: ProviderInfo returns `models: list[{id, name, is_default}]` instead of just `default_model`
- [ ] Correct model IDs per the table above
- [ ] Frontend: combobox (dropdown + free text) replaces plain text input in NewSessionDialog
- [ ] Selecting a provider updates the model list to show that provider's models
- [ ] User can still type a custom model ID not in the list
- [ ] Default model is pre-selected when switching providers
- [ ] Existing tests updated, new tests for model list rendering
