# Issue #112: Clean up NativeEngine Anthropic SDK usage

## Background

Split from #110. After #110 removes `CODEHIVE_ANTHROPIC_API_KEY` and #111 adds `CodexCLIEngine`, the `NativeEngine` is only used for Z.ai (which uses an Anthropic-compatible API). Consider:

1. Renaming `NativeEngine` to `ZaiEngine` or `AnthropicCompatibleEngine` for clarity
2. Or removing `NativeEngine` entirely if Z.ai can be served by a simpler adapter
3. Removing the `anthropic` SDK dependency from the project if no longer needed (Z.ai may need it)

## Requirements

- Audit all usages of `NativeEngine` and `AsyncAnthropic`
- Decide on rename vs removal
- Update `code_app.py` TUI to default to `ClaudeCodeEngine` instead of `NativeEngine`
- Update engine `__init__.py` exports

## Dependencies

- #110 must be `.done.md` first
- #111 should be `.done.md` first (so all CLI engines exist)
