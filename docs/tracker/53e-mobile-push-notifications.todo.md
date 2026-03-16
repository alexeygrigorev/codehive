# 53e: Mobile Push Notifications

## Description
Integrate Firebase Cloud Messaging (FCM) for push notifications. Backend sends push notifications for key events: approval required, session completed/failed, pending questions.

## Implementation Plan

### 1. Firebase setup
- Add `expo-notifications` and `expo-device` to mobile project
- Configure Firebase project, add `google-services.json` to `mobile/`
- `mobile/src/notifications/setup.ts` -- request permissions, get FCM token, register with backend

### 2. Backend notification endpoint
- `POST /api/notifications/register-device` -- accepts `{token, platform, device_id}`
- Store device tokens in new `device_tokens` table or in existing notifications infrastructure
- `backend/codehive/api/schemas/push.py` -- schema for device registration
- `backend/codehive/api/routes/notifications.py` -- extend with device registration endpoint

### 3. Backend push sending
- `backend/codehive/core/push.py` -- send FCM push via `firebase-admin` SDK or HTTP v1 API
- Hook into existing event bus: when `approval.required`, `session.completed`, `session.failed`, or `question.created` events fire, send push to registered devices
- Push payload includes: title, body, data (session_id, event_type) for deep linking

### 4. Mobile notification handling
- `mobile/src/notifications/handler.ts` -- handle received notifications
- Tapping a notification navigates to the relevant screen (session detail, questions, approvals)

## Acceptance Criteria

- [ ] Mobile app requests notification permissions on first launch
- [ ] FCM token is sent to backend via `/api/notifications/register-device`
- [ ] Backend sends push notification when an approval is required
- [ ] Backend sends push notification when a session completes or fails
- [ ] Backend sends push notification when a new pending question is created
- [ ] Tapping a push notification navigates to the relevant screen in the app
- [ ] `uv run pytest tests/test_push.py -v` passes with 3+ tests

## Test Scenarios

### Unit: Device registration
- POST valid device token, verify 201 and token stored
- POST duplicate token, verify no duplicate created

### Unit: Push sending
- Mock FCM, trigger approval event, verify push payload is correct
- Mock FCM, trigger session.failed event, verify push sent with session_id

### Integration: End-to-end
- Register a device token
- Create an approval event
- Verify push notification was dispatched (via mock)

## Dependencies
- Depends on: #53a (scaffolding), #07 (event bus)
