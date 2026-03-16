# 53: Android Mobile App (Parent)

## Description
Build a React Native (Expo) mobile app in `mobile/` that connects to the codehive backend API. The app provides monitoring, quick actions, and voice input -- not a full IDE. This is a large feature split into sub-issues.

## Sub-Issues
- **53a** -- Expo project scaffolding, navigation, API client, auth token storage
- **53b** -- Dashboard screen (projects list, sessions list, status badges)
- **53c** -- Session detail screen (chat view, status, send messages)
- **53d** -- Questions and approvals screens (answer questions, approve/reject actions)
- **53e** -- Push notifications via Firebase Cloud Messaging
- **53f** -- Voice input (Android speech recognition, record and send)

## What it is NOT
- Not a full IDE -- no code editing, no diff viewing, no file browsing
- No offline mode (always connected to backend)

## Dependencies
- Depends on: #01 (backend API), #05 (session CRUD), #07 (event bus/WebSocket)
- #53c depends on #53a, #53b
- #53d depends on #53a
- #53e depends on #53a
- #53f depends on #53c
