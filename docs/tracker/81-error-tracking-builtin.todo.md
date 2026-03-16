# 81: Built-in Error Tracking

## Description
Add error aggregation using our own event bus and persistent logs. Error dashboard endpoint, error count by type, alerting via Telegram/push when error rate spikes. No external service — uses existing infrastructure.

## Dependencies
- Depends on: #07 (event bus), #51 (persistent logs), #32 (Telegram notifications)
