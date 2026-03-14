# 45: Agent Modes Backend Logic

## Description
Implement the behavioral logic for agent modes (Brainstorm, Interview, Planning, Execution, Review). Each mode changes the agent's system prompt, available tools, and behavioral constraints. Support fluid mode switching within a session.

## Scope
- `backend/codehive/core/modes.py` -- Mode definitions: system prompt templates, tool sets, behavioral rules per mode
- `backend/codehive/engine/native.py` -- Extend to apply mode-specific system prompts and tool filtering
- `backend/codehive/api/routes/sessions.py` -- Extend to support mode switching endpoint
- `backend/tests/test_modes.py` -- Mode switching and constraint tests

## Mode behaviors
- **Brainstorm**: Free-form ideation, no code tools, open-ended questions
- **Interview**: Structured questions (3-7 per batch), save answers to project knowledge
- **Planning**: Task decomposition, milestone creation, no code editing
- **Execution**: Full tool access, standard coding mode
- **Review**: Read-only tools, evaluation focus, improvement suggestions

## Dependencies
- Depends on: #09 (engine adapter for tool filtering and system prompts)
- Depends on: #05 (session mode field)
