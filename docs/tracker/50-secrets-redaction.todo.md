# 50: Secrets Redaction in Logs and Output

## Description
Implement automatic redaction of secrets and sensitive values in agent logs, stdout/stderr output, and event data. Ensure no raw API keys, passwords, or environment variable values appear in stored logs or streamed events.

## Scope
- `backend/codehive/core/redaction.py` -- Redaction engine: pattern-based detection of secrets (API keys, tokens, passwords), replacement with masked values
- `backend/codehive/execution/shell.py` -- Extend to redact stdout/stderr before logging/streaming
- `backend/codehive/core/events.py` -- Extend to redact event data before storage and publishing
- `backend/tests/test_redaction.py` -- Redaction tests (various secret patterns)

## Dependencies
- Depends on: #08 (execution layer for shell output)
- Depends on: #07 (event bus for event data)
- Depends on: #13 (secrets management foundation)
