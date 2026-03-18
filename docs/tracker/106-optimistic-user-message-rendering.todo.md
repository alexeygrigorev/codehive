# Issue #106: Optimistic user message rendering

## Problem

When a user sends a message in the chat, the user's message bubble does not appear immediately. Instead, it arrives via SSE event after ~100-200ms. During this brief window, the "No messages yet. Start the conversation." placeholder is visible alongside the thinking indicator dots.

This was observed during issue #105 (Streaming responses and thinking indicator) acceptance review. Screenshot evidence: `/tmp/e2e-105-input-disabled.png` shows "No messages yet" text with thinking dots but no user message bubble.

## Expected Behavior

When the user presses Send or Enter:
1. The user's message should appear instantly in a blue bubble (optimistic rendering)
2. The thinking indicator should appear below the user's message
3. The SSE event confirming the message should reconcile with the optimistic message (no duplicates)

## Origin

Descoped from issue #105 (non-blocking UX polish). The current behavior does not break functionality but creates a brief jarring moment.

## Dependencies

- Issue #105 must be `.done.md` first (streaming infrastructure)
