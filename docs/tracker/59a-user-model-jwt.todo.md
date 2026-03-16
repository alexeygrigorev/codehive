# 59a: User Model + JWT Authentication

## Description
Add a User model to the database, implement JWT token generation/validation, and protect all API endpoints with authentication middleware.

## Implementation Plan

### 1. User model
- Add to `backend/codehive/db/models.py`:
  ```
  class User(Base):
      __tablename__ = "users"
      id: UUID, primary_key
      email: str, unique, not null
      username: str, unique, not null
      password_hash: str, not null
      is_active: bool, default True
      is_admin: bool, default False
      created_at: datetime
      workspace_id: UUID, FK to workspaces (nullable, for default workspace)
  ```
- Alembic migration for the users table

### 2. Password hashing
- `backend/codehive/core/auth.py`
- Use `passlib[bcrypt]` for password hashing
- `hash_password(plain)`, `verify_password(plain, hashed)`

### 3. JWT token handling
- `backend/codehive/core/jwt.py`
- `create_access_token(user_id, expires_delta)` -- creates JWT with `sub` claim
- `create_refresh_token(user_id)` -- longer-lived refresh token
- `decode_token(token)` -- validates and returns payload
- Secret key from config (`CODEHIVE_SECRET_KEY`)
- Access token expiry: 30 minutes; refresh token expiry: 7 days
- Use `python-jose[cryptography]` or `PyJWT`

### 4. Auth endpoints
- `backend/codehive/api/routes/auth.py`
- `POST /api/auth/register` -- create user (email, username, password) -> returns tokens
- `POST /api/auth/login` -- email + password -> returns access_token + refresh_token
- `POST /api/auth/refresh` -- refresh_token -> returns new access_token
- `GET /api/auth/me` -- returns current user info (requires auth)

### 5. Auth dependency
- `backend/codehive/api/deps.py` -- add `get_current_user` dependency
- Reads `Authorization: Bearer {token}` header
- Decodes JWT, loads user from DB
- Returns 401 if token is invalid or expired
- Apply to all existing routes (except health check and auth endpoints)

### 6. Schemas
- `backend/codehive/api/schemas/auth.py`
- `UserCreate`, `UserLogin`, `TokenResponse`, `UserRead`

## Acceptance Criteria

- [ ] `users` table exists with email, username, password_hash, is_active, is_admin
- [ ] `POST /api/auth/register` creates a user and returns JWT tokens
- [ ] `POST /api/auth/login` with correct credentials returns JWT tokens
- [ ] `POST /api/auth/login` with wrong credentials returns 401
- [ ] `POST /api/auth/refresh` with valid refresh token returns new access token
- [ ] `GET /api/auth/me` with valid token returns user info
- [ ] `GET /api/auth/me` without token returns 401
- [ ] All existing API endpoints (except /api/health, /api/auth/*) require authentication
- [ ] Passwords are stored as bcrypt hashes, never in plaintext
- [ ] `uv run pytest tests/test_auth.py -v` passes with 10+ tests

## Test Scenarios

### Unit: Password hashing
- Hash a password, verify it is not plaintext
- Verify correct password matches hash
- Verify wrong password does not match hash

### Unit: JWT tokens
- Create access token, decode it, verify user_id in payload
- Create expired token, verify decode raises error
- Create refresh token, verify longer expiry

### Integration: Auth endpoints
- Register a new user, verify 201 and tokens returned
- Register duplicate email, verify 409 conflict
- Login with correct credentials, verify 200 and tokens
- Login with wrong password, verify 401
- Refresh with valid token, verify new access token
- Call /api/auth/me with token, verify user info

### Integration: Protected routes
- Call GET /api/projects without token, verify 401
- Call GET /api/projects with valid token, verify 200
- Call GET /api/health without token, verify 200 (unprotected)

## Dependencies
- Depends on: #01 (FastAPI), #03 (DB models)
