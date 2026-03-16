# 53f: Mobile Voice Input

## Description
Add voice input to the mobile app using Android speech recognition. User can tap a microphone button, speak, see a transcript preview, optionally edit it, and send to the current session chat. The voice input populates the existing text input field so the user reviews before sending via the normal Send button.

## Implementation Plan

### 1. Voice recognition hook
- Install `@react-native-voice/voice` (compatible with Expo bare/dev-client workflow) for on-device speech-to-text
- Create `mobile/src/hooks/useVoiceRecognition.ts` -- encapsulates Voice.start(), Voice.stop(), Voice.onSpeechResults, Voice.onSpeechError
- Hook returns: `{ isListening, transcript, error, startListening, stopListening, resetTranscript }`
- Handle permissions (RECORD_AUDIO) -- request at first use, show message if denied

### 2. VoiceButton component
- `mobile/src/components/VoiceButton.tsx` -- microphone icon button placed next to text input in SessionDetailScreen
- Single tap to start listening, tap again to stop (toggle behavior -- simpler and more accessible than hold-to-record)
- Visual states: idle (mic icon), listening (pulsing/red mic icon with "Listening..." label), error (show brief error text)
- Props: `onTranscript: (text: string) => void`, `disabled?: boolean`
- Uses `useVoiceRecognition` hook internally
- testID="voice-button"

### 3. Integration with SessionDetailScreen
- Add VoiceButton between the TextInput and Send button in the input bar
- When voice recognition produces a transcript, populate `inputText` state with it (append if text already exists, separated by space)
- User can then edit the text in the input field and send normally via the existing Send button
- No separate TranscriptPreview component needed -- the existing TextInput serves as the preview/edit area
- Voice button is disabled while a message is being sent

### 4. Error handling
- If speech recognition is unavailable on device, hide the voice button entirely (graceful degradation)
- If recognition returns empty result, do nothing (do not clear existing input)
- If recognition errors out, show a brief toast/message and reset to idle state

## Acceptance Criteria

- [x] `@react-native-voice/voice` (or equivalent Expo-compatible speech-to-text library) is added to `mobile/package.json`
- [x] `mobile/src/hooks/useVoiceRecognition.ts` exists and exports the hook with `isListening`, `transcript`, `error`, `startListening`, `stopListening`, `resetTranscript`
- [x] `mobile/src/components/VoiceButton.tsx` exists with testID="voice-button"
- [x] VoiceButton renders in SessionDetailScreen input bar (between TextInput and Send button)
- [x] Tapping VoiceButton starts speech recognition; tapping again stops it
- [x] VoiceButton shows distinct visual states for idle vs listening (at minimum, different styling or label)
- [x] Recognized speech text populates the existing TextInput (`message-input`) so the user can review/edit before sending
- [x] Sending after voice input uses the same `sendMessage` API call as typed messages (no separate send path)
- [x] If speech recognition is unavailable, VoiceButton does not render (graceful degradation)
- [x] All existing session detail tests continue to pass (no regressions)
- [x] `cd mobile && npx jest` passes with 8+ new tests across voice-related test files

## Test Scenarios

### Unit: useVoiceRecognition hook (`mobile/__tests__/use-voice-recognition.test.ts`)
- Hook initializes with `isListening: false`, `transcript: ""`, `error: null`
- Calling `startListening` sets `isListening: true` and calls Voice.start()
- Calling `stopListening` sets `isListening: false` and calls Voice.stop()
- When Voice.onSpeechResults fires with results, `transcript` updates
- When Voice.onSpeechError fires, `error` is set and `isListening` becomes false
- Calling `resetTranscript` clears transcript and error

### Unit: VoiceButton (`mobile/__tests__/voice-button.test.tsx`)
- Renders a touchable element with testID="voice-button"
- Tapping the button when idle starts listening (verify via mock)
- Tapping the button when listening stops listening (verify via mock)
- Shows different visual indicator when listening vs idle (e.g., different text or style)
- Calls `onTranscript` callback when speech recognition produces a result
- Does not render when speech recognition is unavailable (mock Voice as unavailable)
- Respects `disabled` prop -- does not respond to taps when disabled

### Integration: SessionDetailScreen with voice (`mobile/__tests__/session-detail-voice.test.tsx`)
- Voice button is present in the session detail input bar
- Voice transcript populates the message TextInput
- User can edit voice-populated text and send it
- Sent message goes through the same `sendMessage` API as typed messages

## Dependencies
- Depends on: #53c (session detail screen) -- DONE
- All prior mobile sub-issues (53a-53e) are complete

## Log

### [SWE] 2026-03-16 12:00
- Installed `@react-native-voice/voice` to mobile/package.json
- Created `mobile/src/hooks/useVoiceRecognition.ts` -- hook wrapping Voice.start/stop/onSpeechResults/onSpeechError with isAvailable check
- Created `mobile/src/components/VoiceButton.tsx` -- toggle mic button with testID="voice-button", idle/listening visual states, graceful degradation when unavailable
- Updated `mobile/src/screens/SessionDetailScreen.tsx` -- integrated VoiceButton between TextInput and Send button, voice transcript appends to inputText, button disabled while sending
- Created `mobile/__mocks__/@react-native-voice/voice.ts` -- mock with helpers to simulate speech results/errors
- Files created:
  - mobile/src/hooks/useVoiceRecognition.ts
  - mobile/src/components/VoiceButton.tsx
  - mobile/__mocks__/@react-native-voice/voice.ts
  - mobile/__tests__/use-voice-recognition.test.ts (7 tests)
  - mobile/__tests__/voice-button.test.tsx (7 tests)
  - mobile/__tests__/session-detail-voice.test.tsx (4 tests)
- Files modified:
  - mobile/src/screens/SessionDetailScreen.tsx
  - mobile/package.json (via npm install)
- Tests added: 18 new tests across 3 test files
- Build results: 101 tests pass (26 suites), 0 fail, TypeScript clean
- All existing session detail tests continue to pass (no regressions)
- Known limitations: none

### [QA] 2026-03-16 12:30
- Tests: 101 passed, 0 failed (26 suites), 18 new voice-related tests
- TypeScript: clean (npx tsc --noEmit passes with no errors)
- Acceptance criteria:
  - `@react-native-voice/voice` added to mobile/package.json: PASS
  - useVoiceRecognition hook exists with correct exports (isListening, transcript, error, startListening, stopListening, resetTranscript): PASS
  - VoiceButton.tsx exists with testID="voice-button": PASS
  - VoiceButton renders in SessionDetailScreen between TextInput and Send button: PASS
  - Tapping VoiceButton toggles speech recognition (start/stop): PASS
  - VoiceButton shows distinct visual states for idle vs listening (different text, colors, "Listening..." label): PASS
  - Recognized speech populates TextInput (message-input) for review/edit before sending: PASS
  - Sending after voice input uses same sendMessage API as typed messages: PASS
  - VoiceButton returns null when speech recognition is unavailable (graceful degradation): PASS
  - All existing session detail tests continue to pass (no regressions): PASS
  - 18 new tests across 3 test files (8+ required): PASS
- VERDICT: PASS

### [PM] 2026-03-16 13:00
- Reviewed diff: 7 files changed relevant to this issue (hook, component, mock, 3 test files, SessionDetailScreen integration, package.json)
- Results verified: 101 tests passing (26 suites), 18 new voice-related tests, TypeScript clean -- real data present in QA log
- Code review findings:
  - useVoiceRecognition hook: clean implementation, proper cleanup with mountedRef and Voice.destroy(), correct event wiring via onSpeechResults/onSpeechError setters
  - VoiceButton: correct toggle behavior, graceful degradation (returns null when !isAvailable), accessibility labels present, distinct idle/listening visual states (text "Mic"/"Stop", red background, "Listening..." label)
  - SessionDetailScreen integration: VoiceButton placed correctly between TextInput and Send button, transcript appends to existing input with space separator, button disabled during send via new `sending` state
  - Mock: well-designed with _simulateSpeechResults/_simulateSpeechError helpers enabling clean test assertions
  - Tests are meaningful: hook tests cover init/start/stop/results/error/reset/unavailable, component tests cover render/toggle/visual-states/transcript-callback/unavailable/disabled, integration tests cover presence/population/edit-and-send/same-API-path
- Acceptance criteria: all 11 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
