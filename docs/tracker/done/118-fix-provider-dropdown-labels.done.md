# Issue #118: Fix provider dropdown — wrong labels and stale types

## Problem

The New Session dialog shows wrong provider labels:
- "Z.ai (no key)" appears 3 times (for claude, codex, and zai)
- "OpenAI (no key)" appears 1 time
- Claude and Codex are missing from the labels

Two root causes:
1. `NewSessionDialog.tsx` label mapping only handles "anthropic" and "openai", falls through to "Z.ai" for everything else
2. `web/src/api/providers.ts` ProviderInfo interface still has old schema (api_key_set, base_url) instead of new schema (type, available, reason) from #110
3. Default provider is "anthropic" which no longer exists — should be "claude"

## Fix Applied

Already fixed directly:
- Updated ProviderInfo interface to match backend schema
- Added label mapping for claude, codex, openai, zai
- Changed default provider from "anthropic" to "claude"
- Shows p.available with p.reason instead of p.api_key_set

## Status

FIX APPLIED — needs QA verification and commit.
