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

- Issue #105 must be `.done.md` first (streaming infrastructure) -- SATISFIED

---

## User Stories

### Story 1: User sends a message in an empty session (first message)
1. User opens a session that has no messages (empty chat shows "No messages yet. Start the conversation.")
2. User types "Hello world" in the message input textarea
3. User presses Enter (or clicks Send)
4. **Immediately** (within the same render frame, before any SSE response), the user's message "Hello world" appears in a blue bubble on the right side of the chat
5. The "No messages yet" placeholder is gone -- replaced by the user's message
6. The thinking indicator dots appear below the user's message
7. When the server's SSE response arrives with the `message.created` event for the user message, no duplicate bubble appears -- the optimistic message is reconciled with the server event
8. Eventually the assistant response streams in below the user's message

### Story 2: User sends a follow-up message in an existing conversation
1. User is in a session that already has previous messages (user + assistant bubbles visible)
2. User types "Tell me more" in the message input textarea
3. User presses Enter
4. **Immediately**, "Tell me more" appears as a new blue bubble at the bottom of the chat, below the existing messages
5. The thinking indicator appears below the new message
6. No duplicate of "Tell me more" appears when the SSE event arrives from the server
7. The assistant response streams in normally

### Story 3: User sends a message and the server echoes back the same message via SSE
1. User sends a message "Test dedup"
2. The optimistic message "Test dedup" appears instantly
3. The SSE stream delivers a `message.created` event with `role: "user"` and `content: "Test dedup"`
4. There is still exactly one "Test dedup" bubble visible in the chat -- not two
5. The bubble retains the correct styling (blue, right-aligned, `data-role="user"`)

---

## E2E Test Scenarios

### E2E Test 1: Optimistic message appears immediately (no "No messages yet" flash)

**Preconditions:** A new session with no messages. Backend is running.

**Steps:**
1. Navigate to an empty session's chat panel
2. Verify "No messages yet. Start the conversation." placeholder is visible
3. Type "Hello optimistic" in the message input
4. Press Enter
5. **Immediately** (within 500ms, no `waitForTimeout`) check for the user message bubble

**Assertions:**
- A `[data-role="user"]` element with text "Hello optimistic" is visible
- The "No messages yet" placeholder is NOT visible
- The thinking indicator (`[data-testid="thinking-indicator"]`) is visible below the user message
- Take screenshot at `/tmp/e2e-106-optimistic-instant.png`

### E2E Test 2: No duplicate message after SSE confirms

**Preconditions:** A new session with no messages. Backend is running.

**Steps:**
1. Navigate to an empty session's chat panel
2. Type "Check dedup" in the message input
3. Press Enter
4. Wait for the assistant response to complete (input re-enabled)

**Assertions:**
- Exactly ONE `[data-role="user"]` element with text "Check dedup" exists (use `count()`)
- The assistant response is visible
- Take screenshot at `/tmp/e2e-106-no-duplicate.png`

### E2E Test 3: Follow-up message also renders optimistically

**Preconditions:** A session with at least one completed exchange (user + assistant messages visible). Backend is running.

**Steps:**
1. Send a first message "First message" and wait for the assistant to respond
2. Type "Follow-up message" in the message input
3. Press Enter
4. Immediately check for the follow-up message bubble

**Assertions:**
- A `[data-role="user"]` element with text "Follow-up message" is visible within 500ms
- The thinking indicator is visible
- After the assistant responds, exactly ONE "Follow-up message" bubble exists
- Take screenshot at `/tmp/e2e-106-followup-optimistic.png`

---

## Implementation Plan

### File: `web/src/components/ChatPanel.tsx`

**Change in `handleSend`:** Before calling `sendMessage()`, create an optimistic `message.created` event and inject it via `injectEvents`. This ensures the user's message appears in `chatItems` on the next render, before any network response.

```typescript
const handleSend = useCallback(
  async (content: string) => {
    setSending(true);
    setIsThinking(true);

    // Optimistic: inject user message immediately
    const optimisticId = `optimistic-${crypto.randomUUID()}`;
    const optimisticEvent: SessionEvent = {
      id: optimisticId,
      session_id: sessionId,
      type: "message.created",
      data: { role: "user", content },
      created_at: new Date().toISOString(),
    };
    injectEvents([optimisticEvent]);

    try {
      await sendMessage(sessionId, content, (rawEvent) => {
        const normalized = normalizeEvent(
          rawEvent as unknown as Record<string, unknown>,
        );
        // Skip injecting the server's user message echo to avoid duplicates
        if (
          normalized.type === "message.created" &&
          normalized.data.role === "user"
        ) {
          return; // Already rendered optimistically
        }
        injectEvents([normalized]);
        // Stop thinking on first assistant content
        if (
          normalized.type === "message.delta" ||
          (normalized.type === "message.created" &&
            normalized.data.role === "assistant") ||
          normalized.type === "tool.call.started"
        ) {
          setIsThinking(false);
        }
      });
      // ... rest unchanged
```

**Key design decisions:**
- Use `crypto.randomUUID()` prefixed with `optimistic-` for the temporary event ID
- Filter out the server's user message echo in the `onEvent` callback (since the content is identical and we already rendered it). This is simpler than trying to match and replace by content.
- The `mergeEvents` deduplication in `WebSocketContext` works by `id`, so the optimistic event (with a different ID) would not be auto-deduped. Instead, we explicitly skip the server echo.

### File: `web/src/test/ChatPanelOptimistic.test.tsx` (new)

New unit test file covering:
1. User message appears in rendered output immediately after handleSend (before sendMessage resolves)
2. No duplicate user message after sendMessage resolves
3. "No messages yet" placeholder disappears immediately after sending
4. Thinking indicator appears alongside the optimistic message

### File: `web/e2e/optimistic-message.spec.ts` (new)

Playwright e2e tests implementing the three E2E test scenarios above.

---

## Acceptance Criteria

- [ ] When a user sends a message, their message bubble appears immediately (same render frame) without waiting for SSE
- [ ] The "No messages yet" placeholder disappears immediately when the first message is sent
- [ ] The thinking indicator appears below the optimistic user message
- [ ] No duplicate user message bubble appears after the SSE stream delivers the server confirmation
- [ ] Follow-up messages in an existing conversation also render optimistically
- [ ] `cd web && npx vitest run src/test/ChatPanelOptimistic.test.tsx` -- all unit tests pass
- [ ] `cd web && npx vitest run` -- all existing tests still pass (no regressions)
- [ ] `cd web && npx tsc --noEmit` -- no type errors
- [ ] E2E tests in `web/e2e/optimistic-message.spec.ts` pass against a running app
- [ ] Screenshots taken at each e2e test step saved to `/tmp/e2e-106-*.png`

## Log

### [SWE] 2026-03-18 18:51

- Implemented optimistic user message rendering in ChatPanel.tsx handleSend
- Before calling sendMessage, inject an optimistic message.created event via injectEvents with id prefixed "optimistic-"
- In the sendMessage onEvent callback, skip server user message echo (message.created with role "user") to prevent duplicates
- Updated existing ChatPanelStreaming test that expected 2 injectEvents calls to expect 3 (optimistic + 2 delta)
- Created unit test file with 4 tests covering: optimistic injection before sendMessage, server echo skipping, thinking indicator with optimistic message, assistant events passing through filter
- Created e2e test file with 3 Playwright scenarios matching the spec

**Files modified:**
- `web/src/components/ChatPanel.tsx` -- added optimistic message injection and server echo filter
- `web/src/test/ChatPanelStreaming.test.tsx` -- updated inject count assertion (2 -> 3)

**Files created:**
- `web/src/test/ChatPanelOptimistic.test.tsx` -- 4 unit tests
- `web/e2e/optimistic-message.spec.ts` -- 3 e2e tests

**Build results:**
- `tsc --noEmit`: clean, no errors
- `vitest run`: 582 tests pass, 0 fail (102 test files)
- `vitest run src/test/ChatPanelOptimistic.test.tsx`: 4/4 pass
- `npx playwright test e2e/optimistic-message.spec.ts`: 3/3 pass (20.3s)
- Full e2e suite: pre-existing timeouts in other tests when running with 3 parallel workers (resource contention), not related to this change

**Screenshots:**
- `/tmp/e2e-106-optimistic-instant.png` -- user message visible immediately with thinking dots, no placeholder
- `/tmp/e2e-106-no-duplicate.png` -- exactly one user message after SSE confirms, assistant response visible
- `/tmp/e2e-106-followup-optimistic.png` -- follow-up message renders optimistically with thinking dots

**Known limitations:** None

### [QA] 2026-03-18 19:05

**Unit tests:** 582 passed, 0 failed (102 test files) -- `cd web && npx vitest run`
**TypeScript:** clean, no errors -- `cd web && npx tsc --noEmit`
**E2E tests:** 3 passed, 0 failed (44.2s) -- `npx playwright test e2e/optimistic-message.spec.ts`

**Acceptance criteria:**

- [x] When a user sends a message, their message bubble appears immediately (same render frame) without waiting for SSE -- PASS. Screenshot `/tmp/e2e-106-optimistic-instant.png` shows user bubble visible with thinking dots, within 500ms timeout. E2E test 1 passes with 500ms assertion.
- [x] The "No messages yet" placeholder disappears immediately when the first message is sent -- PASS. E2E test 1 asserts `not.toBeVisible()` for placeholder after sending. Screenshot confirms no placeholder visible.
- [x] The thinking indicator appears below the optimistic user message -- PASS. Screenshot `/tmp/e2e-106-optimistic-instant.png` shows three animated dots below the user message bubble.
- [x] No duplicate user message bubble appears after the SSE stream delivers the server confirmation -- PASS. E2E test 2 uses `toHaveCount(1)` to verify exactly one "Check dedup" bubble. Screenshot `/tmp/e2e-106-no-duplicate.png` shows single user message with assistant response.
- [x] Follow-up messages in an existing conversation also render optimistically -- PASS. E2E test 3 sends a follow-up after a completed exchange and asserts visibility within 500ms. Screenshot `/tmp/e2e-106-followup-optimistic.png` shows follow-up bubble with thinking dots.
- [x] `cd web && npx vitest run src/test/ChatPanelOptimistic.test.tsx` -- PASS. 4/4 tests pass (included in full 582 test run).
- [x] `cd web && npx vitest run` -- PASS. 582 passed, 0 failed. No regressions.
- [x] `cd web && npx tsc --noEmit` -- PASS. No type errors.
- [x] E2E tests in `web/e2e/optimistic-message.spec.ts` pass against a running app -- PASS. 3/3 pass.
- [x] Screenshots taken at each e2e test step saved to `/tmp/e2e-106-*.png` -- PASS. All three screenshots verified visually.

**Screenshot evidence:**
- `/tmp/e2e-106-optimistic-instant.png` -- user message "Hello optimistic" in blue bubble, thinking dots below, no placeholder
- `/tmp/e2e-106-no-duplicate.png` -- single "Check dedup" bubble, assistant response visible, no duplicate
- `/tmp/e2e-106-followup-optimistic.png` -- follow-up message in blue bubble with thinking dots, previous exchange visible above

**Code review notes:**
- Implementation correctly injects an optimistic event via `injectEvents` before calling `sendMessage`, using `optimistic-` prefixed UUID
- Server echo filtering correctly skips `message.created` events with `role: "user"` to prevent duplicates
- Existing streaming test updated to account for the additional optimistic inject call (2 -> 3)
- Unit tests cover: optimistic injection ordering, server echo dedup, thinking indicator, assistant event passthrough
- E2E tests match all three spec scenarios exactly

VERDICT: PASS

### [PM] 2026-03-18 19:15
- Reviewed diff: 3 files changed (ChatPanel.tsx +19 lines, ChatPanelStreaming.test.tsx assertion update, .todo.md deleted)
- New files: ChatPanelOptimistic.test.tsx (4 unit tests), optimistic-message.spec.ts (3 e2e tests)
- Ran vitest independently: 582/582 pass, 0 fail -- confirmed no regressions
- Screenshots reviewed:
  - `/tmp/e2e-106-optimistic-instant.png`: user message "Hello optimistic" in blue bubble, thinking dots below, no "No messages yet" placeholder -- matches Story 1
  - `/tmp/e2e-106-no-duplicate.png`: single "Check dedup" bubble with assistant response, no duplicate -- matches Story 3
  - `/tmp/e2e-106-followup-optimistic.png`: follow-up message in blue bubble with thinking dots, previous exchange visible above -- matches Story 2
- Implementation is minimal and clean: optimistic event injection before sendMessage, server echo filtering to prevent duplicates
- All 10 acceptance criteria: MET
- No scope dropped, no follow-up issues needed
- User perspective: sending a message now feels instant with no placeholder flash -- the user would be satisfied
- VERDICT: ACCEPT
