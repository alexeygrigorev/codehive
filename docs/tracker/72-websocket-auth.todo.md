# 72: WebSocket Authentication

## Description
Add token verification to WebSocket connections for the single-user self-hosted instance. The server already has a single-user auth token (from #59a). WebSocket connections must include this token (via query parameter or first message) and be rejected with proper close codes (4001 Unauthorized) if the token is missing or invalid. No user lookup or multi-tenant logic -- just verify the request carries the correct token.

## Dependencies
- Depends on: #07 (WebSocket), #59a (JWT auth)
