# 53f: Mobile Voice Input

## Description
Add voice input to the mobile app using Android speech recognition. User can record voice, see transcript preview, edit, and send to the current session chat.

## Implementation Plan

### 1. Voice recording
- Add `expo-speech` or `@react-native-voice/voice` for speech-to-text
- `mobile/src/components/VoiceButton.tsx` -- hold-to-record button, shows recording indicator
- On release, stop recording and run speech-to-text

### 2. Transcript preview
- `mobile/src/components/TranscriptPreview.tsx` -- shows recognized text in editable field
- User can edit before sending
- Send button dispatches the text as a regular message to the session

### 3. Integration with session detail
- Add VoiceButton next to the text input in SessionDetailScreen
- Voice input result populates the text input field for review before sending

## Acceptance Criteria

- [ ] Voice button appears on session detail screen next to text input
- [ ] Pressing and holding the voice button starts speech recognition
- [ ] Releasing the button stops recording and shows transcript
- [ ] User can edit the transcript before sending
- [ ] Sending the transcript dispatches it as a regular chat message
- [ ] Works with Android speech recognition API

## Test Scenarios

### Unit: VoiceButton
- Render VoiceButton, verify it is present
- Simulate press, verify recording state is activated
- Simulate release, verify transcript callback is fired

### Unit: TranscriptPreview
- Render with initial transcript, verify text is shown
- Edit text, verify onChange is called
- Tap send, verify onSend is called with edited text

## Dependencies
- Depends on: #53c (session detail screen)
