# Issue #109: Integrate OpenAI Codex as an engine option

## Problem

Currently Codehive only supports the "native" engine (Anthropic/Z.ai Claude). OpenAI's Codex is a coding agent that could be integrated as an alternative engine, giving users the choice of which coding agent to use for their sessions.

## Requirements

- [ ] Add "codex" as a new engine type alongside "native"
- [ ] Integrate OpenAI Codex API for code generation and tool use
- [ ] Users can select Codex when creating a session (web UI and CLI)
- [ ] OpenAI API key configuration (CODEHIVE_OPENAI_API_KEY or similar)
- [ ] Codex sessions stream responses like native sessions
- [ ] Tool calls from Codex are handled the same way as native tool calls

## Notes

- Codex is OpenAI's coding agent — need to research its API surface and capabilities
- May need a new engine class (CodexEngine) similar to NativeEngine
- Should support the same session lifecycle (start, send message, stream response, tool approval)
- Consider whether Codex has its own tool definitions or if we need to map our tools to its format
