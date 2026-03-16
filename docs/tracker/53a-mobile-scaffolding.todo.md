# 53a: Mobile App Scaffolding

## Description
Initialize the React Native (Expo) project in `mobile/`, set up navigation, configure the API client to communicate with the codehive backend, and implement auth token storage.

## Implementation Plan

### 1. Project initialization
- Run `npx create-expo-app mobile --template blank-typescript`
- Configure `app.json` with app name, slug, Android package name
- Add dependencies: `@react-navigation/native`, `@react-navigation/bottom-tabs`, `@react-navigation/native-stack`, `axios`, `@react-native-async-storage/async-storage`

### 2. Navigation structure
- Bottom tab navigator with 4 tabs: Dashboard, Sessions, Questions, Settings
- Stack navigator nested inside each tab for drill-down screens
- `mobile/src/navigation/RootNavigator.tsx` -- main navigator
- `mobile/src/navigation/types.ts` -- typed route params

### 3. API client
- `mobile/src/api/client.ts` -- axios instance with base URL from config, auth token interceptor
- `mobile/src/api/projects.ts` -- `listProjects()`, `getProject(id)`
- `mobile/src/api/sessions.ts` -- `listSessions()`, `getSession(id)`, `sendMessage(id, text)`
- `mobile/src/api/questions.ts` -- `listQuestions()`, `answerQuestion(id, answer)`
- `mobile/src/api/approvals.ts` -- `listPendingApprovals()`, `approve(id)`, `reject(id)`
- Base URL configurable via env or settings screen

### 4. Auth token storage
- `mobile/src/auth/storage.ts` -- save/load/clear JWT token using AsyncStorage
- Token auto-attached to all API requests via axios interceptor
- Settings screen has a field to enter the backend URL and token (manual entry for now, login UI comes with #59)

### 5. WebSocket client
- `mobile/src/api/ws.ts` -- connect to `ws://{backend}/ws/events`, auto-reconnect, parse event JSON
- React context provider `mobile/src/context/EventContext.tsx` for distributing events to screens

## Acceptance Criteria

- [ ] `mobile/` directory contains a working Expo TypeScript project
- [ ] `cd mobile && npx expo start` launches the Metro bundler without errors
- [ ] Bottom tab navigation renders 4 tabs (Dashboard, Sessions, Questions, Settings)
- [ ] API client can be configured with a backend URL
- [ ] Auth token is persisted in AsyncStorage and attached to requests
- [ ] WebSocket client connects and receives events

## Test Scenarios

### Unit: API client
- Create axios instance, verify auth header is attached when token is set
- Verify token is cleared from storage on logout

### Unit: Navigation
- Render RootNavigator, verify 4 tabs are present
- Navigate between tabs, verify correct screen renders

### Integration: Backend connection
- Configure API client with running backend URL
- Call `listProjects()`, verify response matches backend data

## Dependencies
- Depends on: #01 (backend API running)
