# 38: PWA Manifest, Service Worker, and Push Notifications

## Description
Convert the web app into a Progressive Web App with installability, offline caching, and push notifications via service workers. This enables mobile users to install the app and receive alerts when sessions need attention (approval required, session completed/failed, pending questions).

## Scope
- `web/public/manifest.json` -- PWA manifest (name, icons, start_url, display: standalone, theme_color, background_color)
- `web/public/icons/` -- App icons in required sizes (192x192, 512x512 minimum)
- `web/src/service-worker.ts` -- Service worker: app shell caching strategy, push event handler that shows notifications
- `web/src/sw-register.ts` -- Service worker registration logic (register on app load, handle updates)
- `web/src/hooks/usePushNotifications.ts` -- React hook: request Notification permission, subscribe to push via PushManager, send subscription to backend, expose subscription state
- `web/vite.config.ts` -- Update to handle service worker build (or add vite-plugin-pwa)
- `backend/codehive/api/routes/notifications.py` -- POST /api/push/subscribe (store PushSubscription), POST /api/push/unsubscribe, POST /api/push/send (admin/test endpoint)
- `backend/codehive/db/models.py` -- PushSubscription model (id, user_id or device_id, endpoint, p256dh key, auth key, created_at)
- `backend/codehive/core/notifications.py` -- Push notification dispatcher: listens to event bus for notification-worthy events, sends web push via pywebpush
- `backend/tests/test_push_notifications.py` -- Backend push notification tests
- `web/src/test/usePushNotifications.test.tsx` -- Frontend hook tests
- `web/src/test/service-worker.test.ts` -- Service worker registration tests

## Out of Scope
- Native app (React Native) -- separate future issue
- Offline-first data sync (IndexedDB) -- only app shell caching here
- Push notification preferences UI (which event types to subscribe to) -- follow-up issue
- Authentication/user accounts -- subscriptions keyed by device for now

## Dependencies
- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #07 (event bus for notification triggers) -- DONE

## Acceptance Criteria

### PWA Manifest and Installability
- [ ] `web/public/manifest.json` exists with valid fields: `name`, `short_name`, `start_url`, `display: "standalone"`, `theme_color`, `background_color`, `icons` array
- [ ] Icons exist at `web/public/icons/` in at least 192x192 and 512x512 sizes
- [ ] `index.html` includes `<link rel="manifest" href="/manifest.json">`
- [ ] `index.html` includes `<meta name="theme-color">` matching the manifest
- [ ] Running `npx vite build` in `web/` produces a valid build with the manifest in `dist/`

### Service Worker
- [ ] `web/src/service-worker.ts` exists and handles `install`, `activate`, and `fetch` events
- [ ] Service worker implements app shell caching (cache static assets on install, serve from cache with network fallback)
- [ ] Service worker handles `push` events: parses payload JSON, calls `self.registration.showNotification()` with title, body, and icon
- [ ] Service worker handles `notificationclick` events: focuses or opens the app window, navigates to a relevant URL from notification data
- [ ] `web/src/sw-register.ts` registers the service worker on app load and exports a function to get the active registration

### Push Notification Hook
- [ ] `web/src/hooks/usePushNotifications.ts` exports a `usePushNotifications` hook
- [ ] Hook exposes: `permission` state ("default", "granted", "denied"), `subscribe()` function, `unsubscribe()` function, `isSubscribed` boolean
- [ ] `subscribe()` requests Notification permission, gets PushSubscription from `registration.pushManager.subscribe()` with the backend's VAPID public key, and POSTs the subscription to `/api/push/subscribe`
- [ ] `unsubscribe()` calls `subscription.unsubscribe()` and POSTs to `/api/push/unsubscribe`
- [ ] Hook reads VAPID public key from an environment variable or config endpoint

### Backend Push Endpoints
- [ ] `POST /api/push/subscribe` accepts a PushSubscription JSON (endpoint, keys.p256dh, keys.auth), stores it in the database, returns 201
- [ ] `POST /api/push/unsubscribe` accepts an endpoint string, removes the subscription, returns 200
- [ ] `POST /api/push/send` (test/admin endpoint) accepts `{title, body, url}`, sends a web push to all stored subscriptions, returns 200 with delivery count
- [ ] PushSubscription DB model exists with fields: id, endpoint (unique), p256dh, auth, created_at
- [ ] Duplicate subscription to the same endpoint updates instead of creating a duplicate

### Push Notification Dispatcher
- [ ] `backend/codehive/core/notifications.py` contains a dispatcher that listens to the event bus
- [ ] Dispatcher sends web push for these event types: `approval.required`, `session.completed`, `session.failed`, `session.waiting` (pending question)
- [ ] Dispatcher uses `pywebpush` (or equivalent) with VAPID credentials from environment variables (`VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_MAILTO`)
- [ ] Push payload includes: `title`, `body` (human-readable summary), `url` (deep link to the relevant session), `event_type`
- [ ] Failed push deliveries (expired subscriptions, 410 Gone) are handled gracefully: subscription removed from DB, no crash

### Tests
- [ ] `uv run pytest backend/tests/test_push_notifications.py -v` passes with 5+ tests
- [ ] `cd web && npx vitest run src/test/usePushNotifications.test.tsx` passes with 3+ tests
- [ ] `cd web && npx vitest run src/test/service-worker.test.ts` passes with 2+ tests

## Test Scenarios

### Unit: Push Subscription CRUD (backend)
- Store a push subscription via POST /api/push/subscribe, verify it persists in DB
- Store a duplicate subscription (same endpoint), verify it upserts (no duplicate row)
- Unsubscribe via POST /api/push/unsubscribe, verify subscription is removed from DB
- Unsubscribe with a non-existent endpoint, verify 200 (idempotent, no error)

### Unit: Push Notification Dispatch (backend)
- Mock pywebpush.webpush, publish an `approval.required` event, verify webpush called with correct payload
- Mock pywebpush.webpush, publish a `session.completed` event, verify notification sent to all stored subscriptions
- Simulate a 410 Gone response from webpush, verify the stale subscription is deleted from DB
- Verify events outside the notification set (e.g., `file.changed`) do NOT trigger a push

### Unit: Send Endpoint (backend)
- POST /api/push/send with title and body, verify push sent to all subscriptions
- POST /api/push/send with no subscriptions stored, verify 200 with count 0

### Unit: usePushNotifications Hook (frontend)
- Render hook, verify initial state: permission is "default", isSubscribed is false
- Mock PushManager.subscribe, call subscribe(), verify subscription POSTed to backend
- Mock an already-granted permission with existing subscription, verify isSubscribed is true on mount

### Unit: Service Worker Registration (frontend)
- Mock navigator.serviceWorker.register, verify sw-register calls it with the correct path
- Verify service worker handles push event by calling showNotification with parsed payload

### Integration: End-to-End Push Flow
- Store a subscription via the API, then call POST /api/push/send, verify the push payload structure matches expected format (title, body, url fields present)
- Publish an `approval.required` event through the event bus, verify the dispatcher calls webpush for each stored subscription

## Implementation Notes
- Use `pywebpush` for backend VAPID-based web push delivery
- VAPID key pair can be generated with `vapid --gen` from the `py-vapid` package; store in env vars
- The service worker must be served from the root path (`/service-worker.js` or `/sw.js`) for full scope
- Consider `vite-plugin-pwa` (workbox) for production-grade caching, but a manual service worker is acceptable for this issue
- The existing `useNotifications` hook in `web/src/hooks/useNotifications.ts` handles in-app WebSocket notification counts; the new `usePushNotifications` hook is for browser-level Push API notifications -- they are complementary, not overlapping
- Alembic migration needed for the PushSubscription table

## Log

### [SWE] 2026-03-15 13:07
- Implemented full PWA manifest, service worker, push notification endpoints, and dispatcher
- Backend:
  - Added `pywebpush` dependency
  - Added VAPID settings to `config.py` (vapid_private_key, vapid_public_key, vapid_mailto, push_notify_events)
  - Added `PushSubscription` model to `db/models.py` (id, endpoint unique, p256dh, auth, created_at)
  - Added Alembic migration `c3d4e5f6a7b8_add_push_subscriptions.py`
  - Added API schemas in `api/schemas/push.py`
  - Added push routes in `api/routes/notifications.py` (POST /api/push/subscribe, /unsubscribe, /send)
  - Added `PushDispatcher` in `core/notifications.py` (listens to Redis event bus, sends web push for approval.required, session.completed, session.failed, session.waiting)
  - Registered push router in `api/app.py`
  - Updated `tests/test_models.py` to include push_subscriptions table
- Frontend:
  - Added `web/public/manifest.json` with name, short_name, start_url, display: standalone, theme_color, background_color, icons
  - Added placeholder icons at `web/public/icons/` (192x192, 512x512)
  - Updated `index.html` with manifest link and theme-color meta tag
  - Added `web/src/service-worker.ts` (install/activate/fetch/push/notificationclick handlers)
  - Added `web/src/sw-register.ts` (registration + getRegistration)
  - Added `web/src/hooks/usePushNotifications.ts` (permission, subscribe, unsubscribe, isSubscribed)
  - Updated `web/vite.config.ts` for service worker build as separate entry
- Files modified:
  - backend/codehive/config.py
  - backend/codehive/db/models.py
  - backend/codehive/api/app.py
  - backend/tests/test_models.py
  - backend/pyproject.toml (pywebpush added)
- Files created:
  - backend/codehive/api/schemas/push.py
  - backend/codehive/api/routes/notifications.py
  - backend/codehive/core/notifications.py
  - backend/codehive/db/migrations/versions/c3d4e5f6a7b8_add_push_subscriptions.py
  - backend/tests/test_push_notifications.py
  - web/public/manifest.json
  - web/public/icons/icon-192x192.png
  - web/public/icons/icon-512x512.png
  - web/src/service-worker.ts
  - web/src/sw-register.ts
  - web/src/hooks/usePushNotifications.ts
  - web/src/test/usePushNotifications.test.tsx
  - web/src/test/service-worker.test.ts
- Tests added: 17 backend tests, 8 frontend tests (4 hook + 4 SW registration)
- Build results: 994 backend tests pass, 311 frontend tests pass, ruff clean, npm build clean
- Known limitations: Icons are solid-color placeholders (not actual branded icons)

### [QA] 2026-03-15 13:12
- Backend tests: 17 passed, 0 failed (test_push_notifications.py)
- Frontend tests: 8 passed, 0 failed (4 hook + 4 SW registration)
- Full backend suite: 994 passed, 0 failed
- Full frontend suite: 311 passed, 0 failed
- Ruff check: clean
- Ruff format: clean
- Frontend build: clean (manifest.json, icons, and service-worker.js in dist/)
- Acceptance criteria:
  - PWA Manifest and Installability (5 items): PASS
  - Service Worker (5 items): PASS
  - Push Notification Hook (5 items): PASS
  - Backend Push Endpoints (5 items): PASS
  - Push Notification Dispatcher (5 items): PASS
  - Tests (3 items): PASS
- Notes: 1 minor RuntimeWarning in test_redis_disconnect_logs_and_continues (unawaited coroutine from AsyncMock) -- non-blocking, matches existing pattern in test_telegram_notifications.py
- VERDICT: PASS

### [PM] 2026-03-15 13:25
- Reviewed diff: 9 modified files + 13 new files (22 total)
- Results verified: real data present -- 994 backend tests pass, 311 frontend tests pass, ruff clean, build clean
- Acceptance criteria: all 22 met
  - PWA Manifest and Installability (5/5): manifest.json valid, icons present, index.html links correct, theme-color matches, build produces dist with manifest
  - Service Worker (5/5): install/activate/fetch/push/notificationclick all handled, app shell caching with network fallback, showNotification with parsed payload, notificationclick navigates/focuses
  - Push Notification Hook (5/5): usePushNotifications exports permission/isSubscribed/subscribe/unsubscribe, VAPID key from VITE_VAPID_PUBLIC_KEY env var, subscribe POSTs to backend, unsubscribe calls both browser and backend
  - Backend Push Endpoints (5/5): subscribe returns 201, unsubscribe returns 200 idempotently, send returns 200 with delivery count, PushSubscription model correct, duplicate endpoint upserts
  - Push Notification Dispatcher (5/5): PushDispatcher listens to Redis session:*:events, handles all 4 event types, uses pywebpush with VAPID from env, payload has title/body/url/event_type, 410 Gone removes stale subscription
  - Tests (3/3): 17 backend tests (5+ required), 4 hook tests (3+ required), 4 SW tests (2+ required)
- Code quality: clean, follows existing patterns (mirrors TelegramDispatcher architecture), proper async/await, good separation of concerns (schemas/routes/dispatcher/model)
- Follow-up issues created: none needed
- VERDICT: ACCEPT
