# Issue #98: Voice recording UX — sound wave visualization and feedback

## Problem

The voice input feature (web and mobile) has no visual feedback during recording. The user can't tell if it's actually capturing audio. Need a live sound wave / waveform visualization so it's clear recording is active.

## Requirements

- [ ] Show a live audio waveform while recording (using Web Audio API / AnalyserNode)
- [ ] Pulsing or animated indicator when recording is active
- [ ] Show recording duration (elapsed time)
- [ ] Clear visual states: idle → recording → processing → done
- [ ] Stop button to end recording
- [ ] Web: waveform in the chat input area
- [ ] Mobile: waveform on the voice input screen

## Notes

- Web Audio API's AnalyserNode provides frequency/time-domain data for waveform rendering
- Canvas or SVG for the waveform visualization
- Keep it lightweight — no heavy audio processing libraries
- The waveform doesn't need to be perfectly accurate, just responsive to audio level
