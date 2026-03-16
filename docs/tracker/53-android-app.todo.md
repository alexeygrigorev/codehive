# 53: Android Mobile App

## Description
Build a native Android app using React Native (or Expo) that connects to the codehive backend API. The app should provide monitoring, quick actions, and voice input — not a full IDE.

## Scope
- `mobile/` directory — React Native / Expo project
- Screens: Dashboard (projects + sessions), Session detail (chat + status), Questions, Approvals
- Push notifications via Firebase Cloud Messaging
- Voice input (Android speech recognition)
- Quick actions: approve/reject, answer questions, start/stop sessions
- Connects to backend via same REST API + WebSocket as web app

## Key features
- Session status monitoring with color-coded badges
- Inline approval buttons (approve/reject from notification)
- Voice message recording and sending
- Pending questions list with inline answer
- Session chat (read + send messages)
- Open issues list per project (from issue tracker API #46)
- Push notifications for: approval required, session completed/failed, pending questions

## What it is NOT
- Not a full IDE — no code editing, no diff viewing, no file browsing
- No offline mode (always connected to backend)

## Dependencies
- Depends on: #01 (backend API), #05 (session CRUD), #07 (event bus/WebSocket)
