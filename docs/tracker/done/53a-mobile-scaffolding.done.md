# 53a: Mobile App Scaffolding

## Description
Initialize the React Native (Expo) project in `mobile/`, set up navigation, configure the API client to communicate with the codehive backend, and implement auth token storage. Target platform is Android only.

## Implementation Plan

### 1. Project initialization
- Run `npx create-expo-app mobile --template blank-typescript`
- Configure `app.json` with app name (`Codehive`), slug (`codehive`), Android package name (`com.codehive.mobile`)
- Remove iOS-specific config from `app.json` (Android-only target)
- Add dependencies: `@react-navigation/native`, `@react-navigation/bottom-tabs`, `@react-navigation/native-stack`, `axios`, `@react-native-async-storage/async-storage`, `react-native-screens`, `react-native-safe-area-context`
- Set up Jest with `jest-expo` preset for testing

### 2. Navigation structure
- Bottom tab navigator with 4 tabs: Dashboard, Sessions, Questions, Settings
- Stack navigator nested inside each tab for drill-down screens
- `mobile/src/navigation/RootNavigator.tsx` -- main navigator
- `mobile/src/navigation/types.ts` -- typed route params
- Placeholder screens for each tab (text label identifying the screen)

### 3. API client
- `mobile/src/api/client.ts` -- axios instance with base URL from config, auth token interceptor
- `mobile/src/api/projects.ts` -- `listProjects()`, `getProject(id)`
- `mobile/src/api/sessions.ts` -- `listSessions(projectId)`, `getSession(id)`, `sendMessage(id, text)`
- `mobile/src/api/questions.ts` -- `listQuestions()`, `answerQuestion(id, answer)`
- `mobile/src/api/approvals.ts` -- `listPendingApprovals()`, `approve(id)`, `reject(id)`
- Base URL configurable via Settings screen (stored in AsyncStorage)

### 4. Auth token storage
- `mobile/src/auth/storage.ts` -- `saveToken(token)`, `loadToken()`, `clearToken()` using AsyncStorage
- Token auto-attached to all API requests via axios request interceptor
- Settings screen has text inputs for backend URL and JWT token (manual entry for now, login UI comes with #59c)

### 5. WebSocket client
- `mobile/src/api/ws.ts` -- connect to `ws://{backend}/api/sessions/{id}/ws`, auto-reconnect on disconnect, parse event JSON
- React context provider `mobile/src/context/EventContext.tsx` for distributing events to screens
- Reconnect with exponential backoff (1s, 2s, 4s, max 30s)

## Acceptance Criteria

- [ ] `mobile/` directory contains an Expo TypeScript project with `package.json`, `app.json`, `tsconfig.json`
- [ ] `cd mobile && npx tsc --noEmit` passes with zero type errors
- [ ] `cd mobile && npx jest --passWithNoTests` runs successfully (test infrastructure works)
- [ ] `app.json` targets Android only (no iOS bundle identifier configured)
- [ ] `mobile/src/navigation/RootNavigator.tsx` exists and exports a bottom-tab navigator with exactly 4 tabs: Dashboard, Sessions, Questions, Settings
- [ ] `mobile/src/navigation/types.ts` exports typed route param lists for all navigators
- [ ] `mobile/src/api/client.ts` exports an axios instance that reads base URL from AsyncStorage and attaches an `Authorization: Bearer <token>` header when a token is stored
- [ ] `mobile/src/api/projects.ts` exports `listProjects()` and `getProject(id)` calling `GET /api/projects` and `GET /api/projects/{id}`
- [ ] `mobile/src/api/sessions.ts` exports `listSessions(projectId)`, `getSession(id)`, `sendMessage(id, text)` calling the correct backend endpoints
- [ ] `mobile/src/api/questions.ts` exports `listQuestions()` and `answerQuestion(id, answer)`
- [ ] `mobile/src/api/approvals.ts` exports `listPendingApprovals()`, `approve(id)`, `reject(id)`
- [ ] `mobile/src/auth/storage.ts` exports `saveToken`, `loadToken`, `clearToken` functions using AsyncStorage
- [ ] `mobile/src/api/ws.ts` exports a WebSocket client that connects to `/api/sessions/{id}/ws` and reconnects automatically
- [ ] `mobile/src/context/EventContext.tsx` exports a React context provider that distributes WebSocket events
- [ ] A Settings screen exists with text inputs for backend URL and auth token, values persisted in AsyncStorage
- [ ] All tests pass: `cd mobile && npx jest` reports zero failures

## Test Scenarios

### Unit: Auth token storage
- Call `saveToken("abc123")`, then `loadToken()` returns `"abc123"`
- Call `clearToken()`, then `loadToken()` returns `null`
- After `saveToken`, the axios instance includes `Authorization: Bearer abc123` header on requests

### Unit: API client configuration
- When no base URL is stored, axios instance uses a sensible default (e.g. `http://localhost:8000`)
- When base URL is set to `http://10.0.0.5:8000`, all API calls use that base URL
- When no token is stored, requests do not include an Authorization header

### Unit: API modules
- `listProjects()` calls `GET /api/projects` and returns the response data
- `getProject("uuid")` calls `GET /api/projects/uuid`
- `listSessions("project-uuid")` calls `GET /api/projects/project-uuid/sessions`
- `sendMessage("session-uuid", "hello")` calls `POST /api/sessions/session-uuid/messages` with body `{content: "hello"}`
- `answerQuestion("q-uuid", "yes")` calls the correct endpoint with the answer payload
- `approve("a-uuid")` and `reject("a-uuid")` call the correct approval endpoints

### Unit: WebSocket client
- WebSocket client constructs the correct URL: `ws://{base}/api/sessions/{id}/ws`
- On connection close, client schedules a reconnect
- Parsed JSON events are dispatched through the EventContext

### Unit: Navigation
- Render RootNavigator, verify 4 tab buttons are present with labels: Dashboard, Sessions, Questions, Settings
- Each tab renders its placeholder screen

### Snapshot: Settings screen
- Settings screen renders text inputs for backend URL and token
- Entering a URL and token, then pressing save, persists values to AsyncStorage

## Dependencies
- Depends on: #01 (backend API running -- done)
- Depends on: #05 (session CRUD API -- done)
- Depends on: #07 (event bus / WebSocket -- done)
- All dependencies are satisfied (in `done/`).

## Log

### [SWE] 2026-03-16 11:45
- Scaffolded Expo TypeScript project in `mobile/` using `create-expo-app --template blank-typescript`
- Configured `app.json`: name "Codehive", slug "codehive", Android package `com.codehive.mobile`, removed iOS config
- Installed dependencies: @react-navigation/native, @react-navigation/bottom-tabs, @react-navigation/native-stack, axios, @react-native-async-storage/async-storage, react-native-screens, react-native-safe-area-context
- Installed dev dependencies: jest, jest-expo, @types/jest, @testing-library/react-native
- Configured Jest with `jest-expo` preset in package.json
- Created navigation structure: RootNavigator with 4 bottom tabs (Dashboard, Sessions, Questions, Settings)
- Created typed route param lists in `src/navigation/types.ts`
- Created placeholder screens for all 4 tabs
- Created Settings screen with text inputs for backend URL and auth token, persisted via AsyncStorage
- Created auth token storage module (`src/auth/storage.ts`): saveToken, loadToken, clearToken
- Created axios API client (`src/api/client.ts`) with configurable base URL (default http://10.0.2.2:7433) and auth token interceptor
- Created API modules: projects.ts, sessions.ts, questions.ts, approvals.ts -- all calling correct backend endpoints
- Created WebSocket client (`src/api/ws.ts`) with auto-reconnect and exponential backoff (1s-30s max)
- Created EventContext provider (`src/context/EventContext.tsx`) for distributing WebSocket events
- Created AsyncStorage mock for tests (`__mocks__/@react-native-async-storage/async-storage.ts`)
- Updated App.tsx to use RootNavigator wrapped in EventProvider
- Files created:
  - mobile/src/navigation/RootNavigator.tsx
  - mobile/src/navigation/types.ts
  - mobile/src/screens/DashboardScreen.tsx
  - mobile/src/screens/SessionsScreen.tsx
  - mobile/src/screens/QuestionsScreen.tsx
  - mobile/src/screens/SettingsScreen.tsx
  - mobile/src/api/client.ts
  - mobile/src/api/projects.ts
  - mobile/src/api/sessions.ts
  - mobile/src/api/questions.ts
  - mobile/src/api/approvals.ts
  - mobile/src/api/ws.ts
  - mobile/src/auth/storage.ts
  - mobile/src/context/EventContext.tsx
  - mobile/__mocks__/@react-native-async-storage/async-storage.ts
  - mobile/__tests__/auth-storage.test.ts
  - mobile/__tests__/api-client.test.ts
  - mobile/__tests__/api-modules.test.ts
  - mobile/__tests__/websocket.test.ts
  - mobile/__tests__/navigation.test.tsx
  - mobile/__tests__/settings-screen.test.tsx
- Files modified: mobile/App.tsx, mobile/app.json, mobile/package.json
- Tests added: 31 tests across 6 test suites
- Build results: 31 tests pass, 0 fail; tsc --noEmit clean (zero type errors)
- Known limitations: act() warnings in settings screen tests from async useEffect (cosmetic, not functional)

### [QA] 2026-03-16 12:10
- Tests: 31 passed, 0 failed (6 test suites)
- TypeScript: `tsc --noEmit` clean, zero type errors
- Acceptance criteria:
  1. `mobile/` contains Expo TS project with package.json, app.json, tsconfig.json: PASS
  2. `tsc --noEmit` passes with zero errors: PASS
  3. `npx jest --passWithNoTests` runs successfully: PASS
  4. `app.json` targets Android only (no iOS bundle identifier): PASS
  5. RootNavigator.tsx exports bottom-tab navigator with 4 tabs (Dashboard, Sessions, Questions, Settings): PASS
  6. types.ts exports typed route param lists for all navigators: PASS
  7. client.ts exports axios instance with base URL from AsyncStorage and Bearer token header: PASS
  8. projects.ts exports listProjects() and getProject(id) calling correct endpoints: PASS
  9. sessions.ts exports listSessions(projectId), getSession(id), sendMessage(id, text) calling correct endpoints: PASS
  10. questions.ts exports listQuestions() and answerQuestion(id, answer): PASS
  11. approvals.ts exports listPendingApprovals(), approve(id), reject(id): PASS
  12. auth/storage.ts exports saveToken, loadToken, clearToken using AsyncStorage: PASS
  13. ws.ts exports WebSocket client connecting to /api/sessions/{id}/ws with auto-reconnect: PASS
  14. EventContext.tsx exports React context provider distributing WebSocket events: PASS
  15. Settings screen with text inputs for backend URL and auth token, persisted in AsyncStorage: PASS
  16. All tests pass with zero failures: PASS
- Note: act() warnings in settings screen tests are cosmetic (async useEffect in test environment), not blocking
- VERDICT: PASS

### [PM] 2026-03-16 12:30
- Reviewed diff: 37 new files in mobile/ (src, tests, config, mocks, assets)
- Results verified: real data present -- 31 tests pass (6 suites), tsc --noEmit clean, all outputs confirmed by running locally
- Acceptance criteria: all 16 met
  1. Expo TS project with package.json, app.json, tsconfig.json: MET
  2. tsc --noEmit zero errors: MET
  3. npx jest runs successfully: MET (31 pass, 0 fail)
  4. app.json Android only (no iOS bundleIdentifier): MET
  5. RootNavigator with 4 bottom tabs (Dashboard, Sessions, Questions, Settings): MET
  6. Typed route param lists in types.ts: MET
  7. Axios client with AsyncStorage base URL and Bearer token interceptor: MET
  8. projects.ts exports listProjects/getProject: MET
  9. sessions.ts exports listSessions/getSession/sendMessage: MET
  10. questions.ts exports listQuestions/answerQuestion: MET
  11. approvals.ts exports listPendingApprovals/approve/reject: MET
  12. auth/storage.ts exports saveToken/loadToken/clearToken: MET
  13. ws.ts WebSocket client with auto-reconnect: MET
  14. EventContext.tsx provider distributing events: MET
  15. Settings screen with URL and token inputs persisted to AsyncStorage: MET
  16. All tests pass with zero failures: MET
- Code quality: clean, strict TypeScript, consistent patterns, meaningful tests (not smoke tests -- verify endpoints, headers, storage, reconnect logic, UI elements)
- Note: cosmetic act() warnings in settings tests from async useEffect -- non-blocking
- Follow-up issues created: none needed
- VERDICT: ACCEPT
