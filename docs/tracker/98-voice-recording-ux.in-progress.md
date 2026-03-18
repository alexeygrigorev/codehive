# Issue #98: Voice recording UX — sound wave visualization and feedback

## Problem

The voice input feature (web) has no visual feedback during recording. The user can't tell if it's actually capturing audio. Need a live sound wave / waveform visualization so it's clear recording is active.

## Scope

Web app only. This issue adds a waveform visualization component and recording timer to the existing voice input flow. It does NOT change the STT logic (`useVoiceInput` hook) or the transcript preview flow.

## Current State

- `useVoiceInput` hook (`web/src/hooks/useVoiceInput.ts`) handles STT via Web Speech API
- `VoiceButton` (`web/src/components/VoiceButton.tsx`) is a simple toggle with `animate-pulse` -- no waveform
- `ChatInput` (`web/src/components/ChatInput.tsx`) integrates voice button and transcript preview
- No Web Audio API usage exists yet -- no `AnalyserNode`, no `getUserMedia` for audio visualization

## Requirements

- [ ] New hook `useAudioWaveform` that captures mic audio via `getUserMedia` and provides waveform data from `AnalyserNode`
- [ ] New component `AudioWaveform` that renders a live sound wave using `<canvas>` element
- [ ] Show elapsed recording duration (mm:ss format) while recording
- [ ] Clear visual states in the recording area: idle (no waveform shown), recording (waveform + timer active), processing (pulsing/loading indicator after stop, while STT finalizes), done (waveform disappears, transcript preview appears)
- [ ] Stop button integrated into the waveform area to end recording
- [ ] Waveform appears inline in the chat input area (replaces or overlays the textarea while recording)
- [ ] Clean up audio resources (stop `MediaStream` tracks, close `AudioContext`) when recording stops or component unmounts

## Technical Approach

### `useAudioWaveform` hook
- Call `navigator.mediaDevices.getUserMedia({ audio: true })` to get a `MediaStream`
- Create an `AudioContext` and `AnalyserNode` (FFT size 256 or 512)
- Connect `MediaStreamSource` -> `AnalyserNode`
- Use `requestAnimationFrame` loop to call `analyser.getByteTimeDomainData()` and expose the `Uint8Array` waveform data
- Return: `{ start, stop, waveformData, isActive, elapsedSeconds }`
- On `stop()`: close AudioContext, stop all MediaStream tracks

### `AudioWaveform` component
- Accepts `waveformData: Uint8Array` and draws on a `<canvas>`
- Simple line-based waveform: iterate over data points, draw connected lines
- Styling: colored line (e.g., blue or red) on transparent background
- Responsive: canvas width matches container, fixed height (~48px)

### Integration into `ChatInput`
- When `isListening` is true, show the waveform + timer + stop button in place of (or overlaying) the textarea
- Start `useAudioWaveform` when voice recording starts, stop when it stops
- After recording stops and before transcript appears, show a brief "processing" state

## Dependencies

- Issue #37 (voice input) -- DONE
- No other blocking dependencies

## Acceptance Criteria

- [ ] `cd web && npx vitest run` passes with 8+ new tests
- [ ] `useAudioWaveform` hook exists at `web/src/hooks/useAudioWaveform.ts` and correctly manages `AudioContext`, `AnalyserNode`, and `MediaStream` lifecycle
- [ ] `AudioWaveform` component exists at `web/src/components/AudioWaveform.tsx` and renders a `<canvas>` element that draws waveform data
- [ ] When recording starts, the chat input area shows the waveform visualization, elapsed timer (mm:ss), and a stop button
- [ ] When recording stops, audio resources are cleaned up (MediaStream tracks stopped, AudioContext closed)
- [ ] Elapsed time displays correctly in mm:ss format and increments each second
- [ ] The waveform is responsive -- canvas width adapts to container width
- [ ] The component handles the case where `getUserMedia` is not available or permission is denied (graceful fallback, no crash)
- [ ] No audio processing libraries are added -- only Web Audio API and Canvas API
- [ ] All four visual states are distinguishable: idle (no waveform), recording (waveform + timer), processing (loading indicator), done (transcript preview)

## Test Scenarios

### Unit: `useAudioWaveform` hook
- Hook initializes with `isActive: false` and null waveform data
- `start()` calls `getUserMedia` and creates `AudioContext` + `AnalyserNode`
- `stop()` closes `AudioContext` and stops `MediaStream` tracks
- `elapsedSeconds` increments while active
- Handles `getUserMedia` rejection gracefully (sets error state, does not throw)
- Cleanup on unmount stops all resources

### Unit: `AudioWaveform` component
- Renders a `<canvas>` element
- Accepts `waveformData` prop and calls canvas drawing methods
- Renders nothing or a flat line when waveformData is all zeros / silence

### Integration: `ChatInput` with waveform
- When `isListening` is true, waveform area is visible in the chat input
- When `isListening` is false, waveform area is not rendered
- Stop button in waveform area triggers `stopListening`
- Elapsed timer is displayed during recording
- After recording stops, processing state is briefly shown before transcript preview appears
