# 164 — Agent spawn configuration: visible and customizable prompts

## Problem
When the orchestrator spawns a sub-agent, the user can't see:
1. What system prompt is being used
2. What arguments/flags are passed to the CLI engine
3. What initial message is sent to the agent
4. What context (task details, acceptance criteria) is included

This makes it hard to debug agent behavior or customize how agents work.

## Expected behavior
1. **Spawn config visible**: When a sub-agent session is created, show the full spawn configuration in the UI (system prompt, CLI args, initial message)
2. **Customizable templates**: The orchestrator's prompt templates (build_instructions output) should be viewable and editable in the UI
3. **Per-role templates**: Each role (PM, SWE, QA, OnCall) has a system prompt template that can be customized
4. **Per-engine args**: CLI engine flags (e.g., `claude --verbose`, `codex --full-auto`) should be configurable per project

## What this looks like
- Session detail page shows a "Spawn Config" section: system prompt, initial message, engine args
- Project settings page has a "Agent Templates" section where you can edit prompt templates per role
- Engine settings: configure CLI flags per engine per project

## Acceptance criteria
- [ ] Session model stores spawn_config (system prompt, initial message, engine args) as JSON
- [ ] Session detail page shows spawn config in an expandable section
- [ ] Project settings: editable prompt templates per role
- [ ] Project settings: configurable CLI engine flags
- [ ] Orchestrator reads custom templates when spawning (falls back to defaults)
- [ ] Changes to templates apply to future spawns (not retroactive)
