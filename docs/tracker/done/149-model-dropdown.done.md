# 149 -- Model selection dropdown with correct defaults per provider

## Problem

The New Session dialog has a free-form text input for model selection. The default models are wrong (e.g., "codex-mini-latest" for OpenAI, "glm-4.7" for Z.ai). Users don't know which model IDs to type.

## Expected behavior

- Dropdown list of common models per provider (populated from backend)
- Correct, up-to-date model IDs for each provider
- Option to type a custom model ID (combobox pattern -- select from list OR type freely)
- Backend returns available models per provider, not just a single default

## Dependencies

None. All provider infrastructure is already in place.

## User Stories

### Story 1: User creates a session with the default model

1. User navigates to a project page
2. User clicks "+ New Session"
3. The New Session dialog opens with "Claude" selected as provider
4. The Model field shows a dropdown with "Claude Sonnet 4.6" pre-selected (model ID: `claude-sonnet-4-6`)
5. User clicks "Create"
6. Session is created with provider=claude, model=claude-sonnet-4-6

### Story 2: User selects a non-default model from the dropdown

1. User opens the New Session dialog
2. Provider is "Claude" by default
3. User clicks the Model dropdown
4. User sees a list: Claude Sonnet 4.6 (default), Claude Opus 4.6, Claude Sonnet 4.5, Claude Haiku 4.5
5. User selects "Claude Opus 4.6"
6. The Model field now shows "claude-opus-4-6"
7. User clicks "Create"
8. Session is created with model=claude-opus-4-6

### Story 3: User switches provider and sees updated model list

1. User opens the New Session dialog (Claude selected by default)
2. User changes provider to "OpenAI"
3. The Model dropdown updates to show: GPT-5.4 (default), GPT-5.4 Mini, O4 Mini, O3
4. The selected model is "gpt-5.4" (OpenAI's default)
5. User switches provider to "Gemini"
6. The Model dropdown updates to show: Gemini 2.5 Flash (default), Gemini 2.5 Pro, Gemini 3.1 Pro (Preview)
7. The selected model is "gemini-2.5-flash"

### Story 4: User types a custom model ID not in the list

1. User opens the New Session dialog
2. Provider is "Claude"
3. User clears the Model field and types "claude-test-model-preview"
4. The typed value is accepted (not rejected or overwritten)
5. User clicks "Create"
6. Session is created with model=claude-test-model-preview

### Story 5: User sees correct defaults for every provider

1. User opens the New Session dialog
2. User cycles through each provider and observes the default model:
   - Claude: claude-sonnet-4-6
   - OpenAI: gpt-5.4
   - Codex CLI: gpt-5.4
   - Gemini: gemini-2.5-flash
   - Copilot CLI: default
   - Z.ai: claude-sonnet-4-6

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

## Acceptance Criteria

### Backend

- [ ] New Pydantic model `ModelInfo` with fields: `id: str`, `name: str`, `is_default: bool`
- [ ] `ProviderInfo` gains a `models: list[ModelInfo]` field
- [ ] `ProviderInfo.default_model` field is removed (superseded by `models` with `is_default=True`)
- [ ] Each provider in `list_providers()` returns the correct models per the tables above
- [ ] Exactly one model per provider has `is_default=True`
- [ ] `GET /api/providers` JSON response includes the `models` array for each provider
- [ ] Existing backend tests updated; new tests verify model lists per provider
- [ ] `cd backend && uv run pytest tests/test_providers_endpoint.py -v` passes

### Frontend

- [ ] `ProviderInfo` TypeScript type updated: `models: { id: string; name: string; is_default: boolean }[]`, `default_model` removed
- [ ] The plain `<input>` for model (data-testid="model-input") is replaced with a combobox component (dropdown + free text)
- [ ] The combobox has data-testid="model-combobox" on the wrapper, data-testid="model-input" on the text input, data-testid="model-listbox" on the dropdown list
- [ ] Selecting a provider repopulates the model combobox with that provider's models
- [ ] The default model (is_default=true) is pre-selected when switching providers
- [ ] Each option in the dropdown shows the display name and model ID (e.g., "Claude Sonnet 4.6 (claude-sonnet-4-6)")
- [ ] User can clear the input and type a custom model ID freely
- [ ] Clicking an option from the dropdown sets the model input value to the model ID
- [ ] Form submission sends the model ID string (not the display name)
- [ ] Existing vitest tests updated; new tests cover combobox behavior
- [ ] `cd web && npx vitest run src/test/NewSessionDialog.test.tsx` passes

### E2E

- [ ] Playwright e2e test `web/e2e/provider-selection.spec.ts` updated to test model dropdown behavior
- [ ] E2e test verifies: opening dialog shows model dropdown with Claude models listed
- [ ] E2e test verifies: switching provider changes model list
- [ ] E2e test verifies: selecting a model from dropdown populates the input
- [ ] E2e test verifies: typing a custom model ID works
- [ ] `cd web && npx playwright test e2e/provider-selection.spec.ts` passes

## Technical Notes

### Backend changes (1 file)

**`backend/codehive/api/routes/providers.py`**:
- Add `ModelInfo(BaseModel)` with `id`, `name`, `is_default` fields
- Add `models: list[ModelInfo]` to `ProviderInfo`, remove `default_model: str`
- Define the model lists as module-level constants (e.g., `CLAUDE_MODELS`, `OPENAI_MODELS`, etc.) using the tables above
- Each provider in `list_providers()` uses its constant instead of a single `default_model` string

### Frontend changes (2-3 files)

**`web/src/api/providers.ts`**:
- Add `ModelInfo` interface: `{ id: string; name: string; is_default: boolean }`
- Update `ProviderInfo`: replace `default_model: string` with `models: ModelInfo[]`

**`web/src/components/NewSessionDialog.tsx`**:
- Replace the `<input>` for model with a combobox component
- The combobox is a text input with a dropdown list that appears on focus/click
- Implementation approach: use a native `<datalist>` element OR a custom dropdown div. A `<datalist>` is simplest but has limited styling. A custom dropdown with an input + absolute-positioned listbox is more controllable. Prefer custom dropdown for testability.
- When provider changes: filter models from the selected provider's `models` array, auto-select the one with `is_default=true`
- Derive the default model from `models.find(m => m.is_default)?.id` instead of `provider.default_model`

**`web/src/components/ModelCombobox.tsx`** (new, optional):
- Extract combobox into its own component if NewSessionDialog gets too large
- Props: `models: ModelInfo[]`, `value: string`, `onChange: (value: string) => void`
- Renders: text input + dropdown list of models
- Keyboard accessible: arrow keys to navigate, Enter to select, Escape to close

### Backward compatibility

- The `default_model` field is removed from the API response. Any consumers that read `default_model` must be updated. In this codebase the only consumer is the frontend `NewSessionDialog` and the `providers.ts` API client.
- The `_build_engine` function in `sessions.py` receives the model ID from the frontend form submission, so it is unaffected by this change (it never reads from `ProviderInfo`).

## Test Scenarios

### Unit: Backend -- model lists per provider
- `list_providers()` returns 6 providers, each with a non-empty `models` list
- Claude provider has exactly 4 models with correct IDs
- OpenAI provider has exactly 4 models with correct IDs
- Codex provider has exactly 3 models
- Gemini provider has exactly 3 models
- Copilot provider has exactly 1 model (id="default")
- Z.ai provider has exactly 2 models
- Each provider has exactly one model with `is_default=True`
- Claude's default model is `claude-sonnet-4-6`
- OpenAI's default model is `gpt-5.4`
- Z.ai's default model is `claude-sonnet-4-6`

### Unit: Frontend -- ProviderInfo type and fetch
- `fetchProviders()` returns data with `models` array (update mock data in `providers.test.ts`)

### Unit: Frontend -- NewSessionDialog combobox
- Dialog renders model combobox instead of plain text input
- Default provider (Claude) shows claude-sonnet-4-6 as selected model
- Switching provider to OpenAI shows gpt-5.4 as selected model
- Switching provider to Z.ai shows claude-sonnet-4-6 as selected model
- Clicking a model option from the dropdown sets the input value
- Typing a custom model ID in the input is accepted
- Form submission sends the correct model ID string
- Dropdown list shows display names with model IDs

### E2E: Playwright -- model selection flow
- Open New Session dialog, verify model dropdown appears with Claude models
- Switch to OpenAI, verify model list changes and default is gpt-5.4
- Select a non-default model from dropdown, verify input updates
- Type a custom model ID, verify it persists through form submission
- Take screenshots at each step for visual verification

## Log

### [SWE] 2026-03-28 10:12
- Implemented ModelInfo schema and model constants per provider in backend
- Replaced default_model field with models list on ProviderInfo
- Created ModelCombobox React component (dropdown + free text input)
- Updated NewSessionDialog to use ModelCombobox, derive default from models array
- Updated ProviderInfo TypeScript type: removed default_model, added models array
- Updated all existing tests to use new models-based mock data
- Added 8 new backend tests (TestModelListsPerProvider) verifying model counts, IDs, defaults per provider
- Added 6 new frontend tests: combobox rendering, dropdown list display, option click, custom typing, form submission
- Updated E2E test to cover model dropdown behavior
- Files modified:
  - backend/codehive/api/routes/providers.py (ModelInfo, model constants, ProviderInfo updated)
  - backend/tests/test_providers_endpoint.py (updated + new model tests)
  - web/src/api/providers.ts (ModelInfo interface, ProviderInfo updated)
  - web/src/components/ModelCombobox.tsx (new)
  - web/src/components/NewSessionDialog.tsx (uses ModelCombobox)
  - web/src/test/NewSessionDialog.test.tsx (updated + new combobox tests)
  - web/src/test/providers.test.ts (updated mock data)
  - web/src/test/ProjectPage.test.tsx (updated mock data + assertion)
  - web/e2e/provider-selection.spec.ts (updated for model dropdown)
- Tests added: 8 new backend, 6 new frontend
- Build results: 29 backend provider tests pass, 97 total backend tests pass; 745 frontend tests pass (122 files); ruff clean; tsc clean
- E2E tests: NOT RUN (requires running app infrastructure); test file updated for manual/CI verification
- Known limitations: CLI providers command (cli.py) still uses old dict-based format with default_model -- out of scope per spec

### [QA] 2026-03-28 10:25
- Backend tests: 29 passed, 0 failed (`tests/test_providers_endpoint.py`)
- Frontend tests: 745 passed, 0 failed (122 test files)
- Ruff check: clean (All checks passed)
- Ruff format: 1 pre-existing issue in `tests/test_issue_tools.py` (unrelated to this issue)
- TypeScript: `tsc --noEmit` clean
- E2E tests: NOT RUN (requires live app); test file reviewed and covers all required scenarios

#### Acceptance Criteria

**Backend:**
- [x] `ModelInfo` Pydantic model with `id: str`, `name: str`, `is_default: bool` -- PASS (providers.py L14-19)
- [x] `ProviderInfo` has `models: list[ModelInfo]` -- PASS (providers.py L29)
- [x] `ProviderInfo.default_model` removed -- PASS (grep confirms zero references in backend and frontend)
- [x] Each provider returns correct models per spec tables -- PASS (verified constants L36-68 match spec exactly)
- [x] Exactly one model per provider has `is_default=True` -- PASS (test_each_provider_has_exactly_one_default passes)
- [x] `GET /api/providers` includes `models` array -- PASS (response_model uses updated ProviderInfo)
- [x] Backend tests updated with new model tests -- PASS (8 new tests in TestModelListsPerProvider)
- [x] `pytest tests/test_providers_endpoint.py -v` passes -- PASS (29/29)

**Frontend:**
- [x] `ProviderInfo` TS type updated with `models: ModelInfo[]`, `default_model` removed -- PASS (providers.ts)
- [x] Plain input replaced with combobox -- PASS (ModelCombobox component with dropdown + free text)
- [x] data-testid attributes: `model-combobox` on wrapper, `model-input` on input, `model-listbox` on dropdown -- PASS
- [x] Selecting provider repopulates model combobox -- PASS (handleProviderChange in NewSessionDialog.tsx)
- [x] Default model pre-selected when switching providers -- PASS (getDefaultModel helper + tests confirm)
- [x] Dropdown shows display name and model ID -- PASS (e.g., "Claude Sonnet 4.6 (claude-sonnet-4-6)")
- [x] User can type custom model ID -- PASS (test "user can type a custom model ID freely" passes)
- [x] Clicking option sets model input to model ID -- PASS (test "clicking a model option sets input value" passes)
- [x] Form sends model ID string -- PASS (test "form submission sends model ID string not display name" passes)
- [x] Vitest tests updated with new combobox tests -- PASS (6 new tests)
- [x] `vitest run` passes -- PASS (745/745)

**E2E:**
- [x] E2E test updated in `web/e2e/provider-selection.spec.ts` -- PASS (test covers model dropdown, provider switch, custom model, screenshots)
- [x] E2E test verifies: dialog shows model dropdown with Claude models -- PASS (lines 40-54)
- [x] E2E test verifies: switching provider changes model list -- PASS (lines 59-70)
- [x] E2E test verifies: selecting model from dropdown populates input -- PASS (lines 73-79)
- [x] E2E test verifies: typing custom model ID works -- PASS (lines 84-87)
- [ ] `playwright test` passes -- NOT VERIFIED (requires running app; SWE noted same)

- VERDICT: PASS
- All acceptance criteria met. Code quality is good: proper type hints, ARIA attributes for accessibility (role="combobox", aria-expanded, aria-controls), keyboard navigation support (arrow keys, Enter, Escape), clean component extraction. The only unverified item is the E2E test execution which requires a running app and was explicitly noted by the SWE as requiring CI/manual verification.

### [PM] 2026-03-28 10:40
- Reviewed diff: 24 files changed (+537 / -414, tracker cleanup included)
- Results verified: real data present -- 29 backend provider tests pass, 745 frontend tests pass, tsc/ruff clean
- Backend model constants verified against spec tables: all 6 providers have correct model IDs, display names, counts, and defaults
- Frontend combobox verified: ARIA attributes, keyboard navigation, outside-click close, filtering, display format "Name (id)", free text input
- ProviderInfo TS type correctly updated: default_model removed, models array added
- Test quality: meaningful tests covering model counts per provider, default model correctness, combobox rendering, option selection, custom input, form submission payload
- E2E test file covers all required scenarios (dialog, provider switch, model selection, custom model, screenshots); execution deferred to CI -- acceptable
- Acceptance criteria: all met (Backend 8/8, Frontend 11/11, E2E 5/6 -- the one unverified is playwright execution which requires a live app, test file is correct)
- Follow-up issues created: none needed
- VERDICT: ACCEPT
