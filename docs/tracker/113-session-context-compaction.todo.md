# Issue #113: Session context compaction with configurable threshold

## Problem

Long coding sessions accumulate messages until they hit the model's context window limit, at which point the session breaks. There's no mechanism to compact/summarize older messages to free up context space, and no visibility into how much context is being used.

## Requirements

### Research (PM must do during grooming)
- [ ] Research how context compaction works in:
  - Claude Code (built-in compaction)
  - Cursor
  - Continue.dev
  - Aider
  - Other AI coding assistants
- [ ] Document findings in the groomed spec: what strategies exist, what works well, tradeoffs

### Compaction Engine
- [ ] Implement context compaction for our own engines (Z.ai, OpenAI API — NOT Claude/Codex CLI which handle their own)
- [ ] Configurable compaction threshold: what percentage of context window triggers compaction (e.g., 80%)
- [ ] Know the context window size per model (lookup table or API)
- [ ] Compaction strategy: summarize older messages while preserving recent context
- [ ] Keep system prompt and recent N messages intact, summarize the rest
- [ ] Store compaction summaries so they can be reviewed

### Context Usage UI
- [ ] Progress bar showing current token usage vs context window size
- [ ] Show in the session header or chat panel
- [ ] Color coding: green (< 50%), yellow (50-80%), red (> 80%)
- [ ] Show exact numbers on hover (e.g., "32,450 / 128,000 tokens")
- [ ] Update in real-time as messages are sent/received

### Configuration
- [ ] Per-session or per-project compaction settings
- [ ] Configurable threshold (default 80% of context window)
- [ ] Option to disable compaction (let it hit the limit and fail)
- [ ] Model context window sizes should be updatable

## Notes

- Claude CLI and Codex CLI handle their own compaction — we only need this for direct API providers (Z.ai, OpenAI API)
- The progress bar is useful for ALL providers — even CLI-based ones could report token usage
- Token counting can use tiktoken for OpenAI models, anthropic token counting for Claude-compatible models
