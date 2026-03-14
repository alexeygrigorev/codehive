# 37: Voice Input

## Description
Add voice input capability to the web app using browser-based speech-to-text (Web Speech API) with Whisper API as a server-side fallback. Include transcript preview before sending and routing to the appropriate chat level.

## Scope
- `web/src/components/VoiceInput.tsx` -- Voice recording button with browser STT (Web Speech API)
- `web/src/hooks/useVoiceInput.ts` -- React hook for voice capture and transcription
- `web/src/components/TranscriptPreview.tsx` -- Preview/edit transcribed text before sending
- `backend/codehive/api/routes/voice.py` -- Server-side STT endpoint (Whisper API fallback)
- `backend/tests/test_voice.py` -- Voice endpoint tests

## Behavior
- Voice capture in browser via Web Speech API (primary)
- If browser STT unavailable, record audio and send to backend for Whisper transcription
- Transcript preview before sending (editable)
- Destructive actions from voice require text confirmation
- Route voice input to global/project/session chat based on context

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #16 (chat panel for sending transcribed messages)
