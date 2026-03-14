# 38: PWA Manifest, Service Worker, and Push Notifications

## Description
Convert the web app into a Progressive Web App with installability, offline caching, and push notifications via service workers. This enables mobile users to install the app and receive alerts.

## Scope
- `web/public/manifest.json` -- PWA manifest (name, icons, start_url, display: standalone)
- `web/src/service-worker.ts` -- Service worker for caching and push notification handling
- `web/src/hooks/usePushNotifications.ts` -- React hook for requesting permission and subscribing
- `backend/codehive/api/routes/notifications.py` -- Push subscription endpoints (store subscription, send push)
- `backend/codehive/core/notifications.py` -- Push notification dispatcher (subscribe to event bus, send web push)
- `backend/tests/test_push_notifications.py` -- Push notification tests

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #07 (event bus for notification triggers)
