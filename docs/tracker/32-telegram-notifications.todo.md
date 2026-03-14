# 32: Telegram Push Notifications and Inline Approvals

## Description
Add push notifications to the Telegram bot for important events, and implement inline keyboard buttons for quick approval/rejection actions.

## Scope
- `backend/codehive/clients/telegram/notifications.py` -- Notification dispatcher: subscribes to event bus, sends Telegram messages for relevant events
- `backend/codehive/clients/telegram/handlers.py` -- Extend with inline keyboard callback handlers
- `backend/codehive/config.py` -- Add Telegram notification settings (chat_id, enabled event types)
- `backend/tests/test_telegram_notifications.py` -- Notification dispatch tests

## Notification triggers
- Approval required
- Session completed
- Session failed
- Sub-agent report ready
- Pending question added

## Dependencies
- Depends on: #31 (Telegram bot base)
- Depends on: #07 (event bus for subscribing to events)
