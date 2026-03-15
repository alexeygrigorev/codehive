# 37: Voice Input

## Description
Add voice input capability to the web app using browser-based speech-to-text (Web Speech API). Users click a microphone button in the chat input area, speak, see an editable transcript preview, and then send or discard. This is a frontend-only feature for the initial implementation -- no server-side Whisper fallback in this issue.

## Scope
- `web/src/hooks/useVoiceInput.ts` -- React hook wrapping browser SpeechRecognition API
- `web/src/components/VoiceButton.tsx` -- Microphone toggle button for the chat input area
- `web/src/components/TranscriptPreview.tsx` -- Editable preview overlay for transcribed text (send/discard)
- `web/src/components/ChatInput.tsx` -- Modified to integrate VoiceButton and TranscriptPreview
- `web/src/test/useVoiceInput.test.tsx` -- Hook tests
- `web/src/test/VoiceButton.test.tsx` -- Button component tests
- `web/src/test/TranscriptPreview.test.tsx` -- Preview component tests
- `web/src/test/ChatInputVoice.test.tsx` -- Integration tests for voice in ChatInput

## Out of Scope (follow-up issues)
- Server-side Whisper API fallback (backend route `voice.py`)
- Destructive action confirmation for voice-originated messages
- Routing voice input to global/project-level chat (currently only session-level chat exists)

## Behavior

### useVoiceInput hook
- Wraps the browser `SpeechRecognition` / `webkitSpeechRecognition` API
- Exposes: `{ isListening, transcript, interimTranscript, isSupported, startListening, stopListening, resetTranscript }`
- `isSupported` returns `false` when the browser lacks the Web Speech API (tests must mock this)
- `startListening()` begins recognition; `stopListening()` ends it
- `transcript` holds the final recognized text; `interimTranscript` holds in-progress text
- Cleans up recognition instance on unmount

### VoiceButton
- Renders a microphone icon button next to the Send button in ChatInput
- Visually indicates recording state (e.g., red/pulsing when active)
- Hidden (not rendered) when `isSupported` is `false`
- Clicking while idle starts listening; clicking while listening stops listening
- Has `aria-label="Start voice input"` / `"Stop voice input"` depending on state

### TranscriptPreview
- Shown when a voice transcript is available (non-empty `transcript` after recording stops)
- Displays the transcribed text in an editable text area
- Two buttons: "Send" (dispatches text via `onSend`) and "Discard" (clears transcript)
- Dismissed after send or discard
- `aria-label="Voice transcript"` on the editable area

### ChatInput integration
- VoiceButton appears in the input bar, between the textarea and the Send button
- When a transcript is ready, TranscriptPreview appears above or replaces the input area
- Sending from TranscriptPreview calls the same `onSend` callback as typing
- After send/discard, returns to normal text input state

## Dependencies
- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #16 (chat panel with ChatInput) -- DONE

## Acceptance Criteria

- [ ] `useVoiceInput` hook exists at `web/src/hooks/useVoiceInput.ts` and exports `isListening`, `transcript`, `interimTranscript`, `isSupported`, `startListening`, `stopListening`, `resetTranscript`
- [ ] `VoiceButton` component renders a microphone button with correct aria-labels for idle/recording states
- [ ] `VoiceButton` is not rendered when `isSupported` is `false`
- [ ] `TranscriptPreview` component displays editable transcript text with Send and Discard buttons
- [ ] Sending from `TranscriptPreview` calls the `onSend` prop and clears the transcript
- [ ] Discarding from `TranscriptPreview` clears the transcript without calling `onSend`
- [ ] `ChatInput` integrates `VoiceButton` in the input bar
- [ ] `ChatInput` shows `TranscriptPreview` when a voice transcript is available
- [ ] All new components have TypeScript types (no `any`)
- [ ] `cd web && npx vitest run` passes with 12+ new voice-related tests across the 4 test files
- [ ] Existing ChatInput tests continue to pass (no regressions)

## Test Scenarios

### Unit: useVoiceInput hook
- Returns `isSupported: false` when SpeechRecognition is not available in the browser
- Returns `isSupported: true` when SpeechRecognition is available (mocked)
- `startListening()` sets `isListening` to `true`
- `stopListening()` sets `isListening` to `false`
- Populates `transcript` with recognized text from the mocked recognition result event
- `resetTranscript()` clears `transcript` back to empty string
- Cleans up (calls `abort()` or `stop()`) on unmount

### Unit: VoiceButton
- Renders a button with `aria-label="Start voice input"` when idle
- Renders a button with `aria-label="Stop voice input"` when recording
- Calls `onStartListening` when clicked in idle state
- Calls `onStopListening` when clicked in recording state
- Not rendered (returns null) when `isSupported` is `false`
- Applies a visual recording indicator class/style when `isListening` is true

### Unit: TranscriptPreview
- Displays the transcript text in an editable textarea with `aria-label="Voice transcript"`
- Calls `onSend` with the (possibly edited) text when Send is clicked
- Calls `onDiscard` (does not call `onSend`) when Discard is clicked
- Allows editing the transcript text before sending

### Integration: ChatInput with voice
- Voice button appears in ChatInput when speech recognition is supported
- Voice button is absent from ChatInput when speech recognition is not supported
- After recording completes, TranscriptPreview is shown with the transcript
- Sending from TranscriptPreview triggers the ChatInput `onSend` callback
- Discarding from TranscriptPreview returns to normal input state without sending

## Log

### [SWE] 2026-03-15 12:56
- Implemented useVoiceInput hook wrapping browser SpeechRecognition/webkitSpeechRecognition API with full TypeScript types (no `any`)
- Created VoiceButton component with idle/recording states, aria-labels, recording indicator class, and null render when unsupported
- Created TranscriptPreview component with editable textarea, Send and Discard buttons
- Modified ChatInput to integrate VoiceButton (between textarea and Send button) and TranscriptPreview (shown above input bar when transcript available)
- Files created: web/src/hooks/useVoiceInput.ts, web/src/components/VoiceButton.tsx, web/src/components/TranscriptPreview.tsx
- Files modified: web/src/components/ChatInput.tsx
- Tests added: 22 new tests across 4 test files (useVoiceInput: 7, VoiceButton: 6, TranscriptPreview: 4, ChatInputVoice: 5)
- Test files created: web/src/test/useVoiceInput.test.tsx, web/src/test/VoiceButton.test.tsx, web/src/test/TranscriptPreview.test.tsx, web/src/test/ChatInputVoice.test.tsx
- Build results: 303 tests pass (all 62 test files), 0 fail, build clean, no regressions
- No external dependencies added -- uses only browser Web Speech API

### [QA] 2026-03-15 13:00
- Tests: 303 passed, 0 failed (62 test files, 22 new voice-related tests)
- Build: clean (tsc + vite, no errors or warnings)
- No `any` types in new components
- Existing ChatInput tests: 7/7 pass (no regressions)
- Acceptance criteria:
  1. useVoiceInput hook exports all 7 required members: PASS
  2. VoiceButton renders with correct aria-labels for idle/recording: PASS
  3. VoiceButton not rendered when isSupported is false: PASS
  4. TranscriptPreview displays editable transcript with Send/Discard: PASS
  5. Sending from TranscriptPreview calls onSend and clears transcript: PASS
  6. Discarding clears transcript without calling onSend: PASS
  7. ChatInput integrates VoiceButton in the input bar: PASS
  8. ChatInput shows TranscriptPreview when transcript available: PASS
  9. All new components have TypeScript types (no any): PASS
  10. 12+ new voice-related tests across 4 test files (22 actual): PASS
  11. Existing ChatInput tests continue to pass: PASS
- VERDICT: PASS

### [PM] 2026-03-15 13:05
- Reviewed diff: 8 files changed (3 new components, 1 new hook, 4 new test files, 1 modified ChatInput)
- Results verified: 303/303 tests pass, 22 new voice-related tests confirmed, build clean
- Code review:
  - useVoiceInput hook: clean SpeechRecognition wrapper, proper TypeScript interfaces (no any), cleanup on unmount via abort(), correct handling of final vs interim transcripts
  - VoiceButton: returns null when unsupported, correct aria-labels for both states, visual recording indicator class (voice-recording + animate-pulse)
  - TranscriptPreview: editable textarea with local state, Send dispatches edited text, Discard calls onDiscard only
  - ChatInput integration: VoiceButton between textarea and Send button, TranscriptPreview shown above input bar when transcript is non-empty and not listening
  - Tests are meaningful: mock SpeechRecognition class with simulateResult method, tests cover all specified scenarios including unmount cleanup, editing transcript before send, and integration flows
- Acceptance criteria: all 11 met
  1. useVoiceInput hook exports all 7 required members: MET
  2. VoiceButton correct aria-labels for idle/recording: MET
  3. VoiceButton not rendered when isSupported is false: MET
  4. TranscriptPreview editable transcript with Send/Discard: MET
  5. Sending from TranscriptPreview calls onSend and clears: MET
  6. Discarding clears without calling onSend: MET
  7. ChatInput integrates VoiceButton: MET
  8. ChatInput shows TranscriptPreview when transcript available: MET
  9. All new components typed, no any: MET
  10. 12+ new tests across 4 files (22 actual): MET
  11. Existing tests pass, no regressions: MET
- Follow-up issues created: none needed (out-of-scope items already documented in issue)
- VERDICT: ACCEPT
