# 59a: User Model + JWT Authentication

## Description

Add a User model to the database, implement JWT token generation/validation, and protect all API endpoints with authentication middleware. This is the backend-only auth foundation; the login UI is handled in #59c.

## Scope

- User SQLAlchemy model + Alembic migration
- Password hashing utilities (bcrypt via passlib)
- JWT access/refresh token creation and validation
- Auth API endpoints: register, login, refresh, me
- `get_current_user` dependency that protects existing routes
- Pydantic schemas for auth request/response bodies
- Config additions: `secret_key`, `access_token_expire_minutes`, `refresh_token_expire_days`

## Out of Scope

- Role-based permissions (handled in #59b)
- Frontend login UI (handled in #59c)
- Email verification, password reset flows

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

### 2. Dependencies to add

- `passlib[bcrypt]` -- password hashing
- `python-jose[cryptography]` or `PyJWT` -- JWT token handling

Add to `backend/pyproject.toml` dependencies.

### 3. Config additions

Add to `backend/codehive/config.py` Settings class:
- `secret_key: str = "change-me-in-production"` (used for JWT signing)
- `access_token_expire_minutes: int = 30`
- `refresh_token_expire_days: int = 7`

These must respect the `CODEHIVE_` env prefix (i.e., `CODEHIVE_SECRET_KEY`).

### 4. Password hashing

- `backend/codehive/core/auth.py`
- Use `passlib` CryptContext with bcrypt scheme
- `hash_password(plain: str) -> str`
- `verify_password(plain: str, hashed: str) -> bool`

### 5. JWT token handling

- `backend/codehive/core/jwt.py`
- `create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str`
- `create_refresh_token(user_id: UUID) -> str`
- `decode_token(token: str) -> dict` -- returns payload with `sub` (user_id as string) and `type` ("access" or "refresh")
- Access tokens include `"type": "access"` claim; refresh tokens include `"type": "refresh"` claim
- Secret key read from Settings

### 6. Auth Pydantic schemas

- `backend/codehive/api/schemas/auth.py`
- `UserCreate(email: str, username: str, password: str)`
- `UserLogin(email: str, password: str)`
- `TokenResponse(access_token: str, refresh_token: str, token_type: str = "bearer")`
- `RefreshRequest(refresh_token: str)`
- `UserRead(id: UUID, email: str, username: str, is_active: bool, is_admin: bool, created_at: datetime)`

### 7. Auth endpoints

- `backend/codehive/api/routes/auth.py`
- `POST /api/auth/register` -- create user (validates unique email+username), returns `TokenResponse` with status 201
- `POST /api/auth/login` -- email + password, returns `TokenResponse` with status 200
- `POST /api/auth/refresh` -- refresh_token in body, returns new `TokenResponse` with status 200
- `GET /api/auth/me` -- requires auth, returns `UserRead`

### 8. Auth dependency

- Update `backend/codehive/api/deps.py` -- add `get_current_user` FastAPI dependency
- Reads `Authorization: Bearer {token}` header
- Decodes JWT (must be access token, not refresh), loads user from DB
- Returns 401 with `{"detail": "..."}` if token missing, invalid, expired, or user not found/inactive
- Register the `auth_router` in `backend/codehive/api/app.py`

### 9. Protect existing routes

- Apply `get_current_user` dependency to all existing routers (projects, sessions, tasks, etc.)
- Exempt: `/api/health`, `/api/auth/*`
- Implementation approach: either add the dependency to each router, or use a middleware/dependency on the app level with an exclusion list

## Acceptance Criteria

- [ ] `User` model exists in `backend/codehive/db/models.py` with columns: `id` (UUID PK), `email` (unique), `username` (unique), `password_hash`, `is_active` (default True), `is_admin` (default False), `created_at`, `workspace_id` (nullable FK)
- [ ] An Alembic migration file creates the `users` table
- [ ] `passlib` and a JWT library are added to `backend/pyproject.toml` dependencies
- [ ] `Settings` in `config.py` includes `secret_key`, `access_token_expire_minutes`, `refresh_token_expire_days`
- [ ] `hash_password()` returns a bcrypt hash; `verify_password()` correctly validates
- [ ] `create_access_token()` produces a JWT with `sub` (user_id) and `type` ("access") claims
- [ ] `create_refresh_token()` produces a JWT with `sub` (user_id) and `type` ("refresh") claims
- [ ] `decode_token()` validates signature, expiry, and returns the payload; raises on invalid/expired tokens
- [ ] `POST /api/auth/register` with valid data returns 201 and `{access_token, refresh_token, token_type}`
- [ ] `POST /api/auth/register` with duplicate email returns 409
- [ ] `POST /api/auth/register` with duplicate username returns 409
- [ ] `POST /api/auth/login` with correct email+password returns 200 and tokens
- [ ] `POST /api/auth/login` with wrong password returns 401
- [ ] `POST /api/auth/login` with nonexistent email returns 401
- [ ] `POST /api/auth/refresh` with valid refresh token returns 200 and new tokens
- [ ] `POST /api/auth/refresh` with expired or invalid token returns 401
- [ ] `GET /api/auth/me` with valid access token returns 200 and user info (id, email, username, is_active, is_admin, created_at)
- [ ] `GET /api/auth/me` without Authorization header returns 401
- [ ] `GET /api/auth/me` with expired token returns 401
- [ ] All existing protected endpoints (e.g., `GET /api/projects`, `POST /api/workspaces`) return 401 without a token
- [ ] `GET /api/health` remains accessible without authentication (returns 200)
- [ ] Passwords are never stored or returned in plaintext -- `password_hash` is a bcrypt hash, and no endpoint returns `password_hash`
- [ ] `uv run pytest tests/test_auth.py -v` passes with 15+ tests covering all of the above

## Test Scenarios

### Unit: Password hashing (`tests/test_auth.py::TestPasswordHashing`)
- `hash_password("secret")` returns a string that is NOT "secret"
- `verify_password("secret", hash_password("secret"))` returns True
- `verify_password("wrong", hash_password("secret"))` returns False
- Two calls to `hash_password("secret")` return different hashes (salt)

### Unit: JWT tokens (`tests/test_auth.py::TestJWT`)
- `create_access_token(user_id)` returns a string; `decode_token()` on it returns payload with `sub` == str(user_id) and `type` == "access"
- `create_refresh_token(user_id)` returns a string; `decode_token()` on it returns payload with `sub` == str(user_id) and `type` == "refresh"
- `create_access_token(user_id, expires_delta=timedelta(seconds=-1))` (already expired) -- `decode_token()` raises an appropriate error
- `decode_token("garbage")` raises an appropriate error
- Access token and refresh token have different `exp` values (refresh is longer-lived)

### Integration: Register endpoint (`tests/test_auth.py::TestRegister`)
- POST `/api/auth/register` with `{email, username, password}` returns 201, body contains `access_token`, `refresh_token`, `token_type == "bearer"`
- The returned `access_token` decodes to a valid payload with the new user's ID
- POST `/api/auth/register` with same email returns 409
- POST `/api/auth/register` with same username (different email) returns 409
- POST `/api/auth/register` with missing fields returns 422

### Integration: Login endpoint (`tests/test_auth.py::TestLogin`)
- Register a user, then POST `/api/auth/login` with correct email+password returns 200 with tokens
- POST `/api/auth/login` with wrong password returns 401
- POST `/api/auth/login` with nonexistent email returns 401

### Integration: Refresh endpoint (`tests/test_auth.py::TestRefresh`)
- Register a user (get refresh_token), POST `/api/auth/refresh` with `{refresh_token}` returns 200 with new tokens
- POST `/api/auth/refresh` with an access token (not refresh) returns 401
- POST `/api/auth/refresh` with invalid token string returns 401

### Integration: Me endpoint (`tests/test_auth.py::TestMe`)
- Register a user, use access_token to GET `/api/auth/me`, returns 200 with user data (id, email, username, is_active, is_admin, created_at); does NOT contain `password_hash`
- GET `/api/auth/me` without Authorization header returns 401
- GET `/api/auth/me` with `Authorization: Bearer invalid` returns 401

### Integration: Protected routes (`tests/test_auth.py::TestProtectedRoutes`)
- GET `/api/projects` without token returns 401
- GET `/api/projects` with valid token returns 200 (or appropriate non-401 code)
- GET `/api/health` without token returns 200 (still unprotected)

## Dependencies

- Depends on: #01 (FastAPI setup) -- DONE
- Depends on: #03 (DB models) -- DONE
- Blocked by: nothing
- Blocks: #59b (Permissions), #59c (Login UI)

## Log

### [SWE] 2026-03-16 14:00
- Implemented User model, JWT auth, password hashing, auth endpoints, and route protection
- Used bcrypt directly (not passlib) due to passlib incompatibility with bcrypt>=4.1 on Python 3.13
- Added `get_current_user` FastAPI dependency with HTTPBearer scheme
- Protected all existing routers via `dependencies=[Depends(get_current_user)]` on `include_router` calls
- Health endpoint and auth endpoints remain public
- Updated all existing test files (24 files) to handle auth: added `true`/`false` SQLite server_default mappings and auth token registration in client fixtures
- Files created:
  - `backend/codehive/core/auth.py` -- password hashing (bcrypt)
  - `backend/codehive/core/jwt.py` -- JWT creation/validation (python-jose)
  - `backend/codehive/api/schemas/auth.py` -- Pydantic schemas
  - `backend/codehive/api/routes/auth.py` -- register, login, refresh, me endpoints
  - `backend/codehive/db/migrations/versions/d4e5f6a7b8c9_add_users_table.py` -- Alembic migration
  - `backend/tests/test_auth.py` -- 26 tests
- Files modified:
  - `backend/codehive/config.py` -- added secret_key, access_token_expire_minutes, refresh_token_expire_days
  - `backend/codehive/db/models.py` -- added User model
  - `backend/codehive/api/deps.py` -- added get_current_user dependency
  - `backend/codehive/api/app.py` -- registered auth_router, added auth dependency to all protected routers
  - `backend/pyproject.toml` -- added passlib[bcrypt], python-jose[cryptography]
  - `backend/tests/test_models.py` -- added "users" to expected tables set
  - 24 existing test files -- SQLite boolean defaults fix + auth registration in client fixtures
- Tests added: 26 tests covering password hashing, JWT tokens, register, login, refresh, me, protected routes, health exemption
- Build results: 1159 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-16 15:30
- Tests: 26 passed in test_auth.py, 1159 passed total, 0 failures
- Ruff check: clean (all files)
- Ruff format: clean (all files)
- Acceptance criteria:
  1. User model with correct columns (id, email, username, password_hash, is_active, is_admin, created_at, workspace_id): PASS
  2. Alembic migration creates users table: PASS
  3. passlib and python-jose in pyproject.toml dependencies: PASS
  4. Settings includes secret_key, access_token_expire_minutes, refresh_token_expire_days: PASS
  5. hash_password() returns bcrypt hash; verify_password() validates: PASS
  6. create_access_token() produces JWT with sub and type=access: PASS
  7. create_refresh_token() produces JWT with sub and type=refresh: PASS
  8. decode_token() validates signature/expiry, raises on invalid/expired: PASS
  9. POST /api/auth/register returns 201 with tokens: PASS
  10. Register duplicate email returns 409: PASS
  11. Register duplicate username returns 409: PASS
  12. POST /api/auth/login returns 200 with tokens: PASS
  13. Login wrong password returns 401: PASS
  14. Login nonexistent email returns 401: PASS
  15. POST /api/auth/refresh returns 200 with new tokens: PASS
  16. Refresh with invalid token returns 401: PASS
  17. GET /api/auth/me returns 200 with user info: PASS
  18. GET /api/auth/me without auth returns 401: PASS
  19. GET /api/auth/me with expired/invalid token returns 401: PASS
  20. Protected endpoints return 401 without token: PASS
  21. GET /api/health remains accessible without auth: PASS
  22. Passwords never stored/returned in plaintext: PASS
- Note: bcrypt used directly instead of passlib CryptContext due to Python 3.13 compatibility -- acceptable
- VERDICT: PASS

### [PM] 2026-03-16 16:00
- Reviewed diff: 36 files changed (+550, -124)
- New files: 6 (core/auth.py, core/jwt.py, api/schemas/auth.py, api/routes/auth.py, migration, test_auth.py)
- Modified files: 30 (config, models, deps, app, pyproject.toml, uv.lock, 24 existing test files)
- Results verified: real data present -- 1159 tests pass, 26 auth tests, ruff clean
- Acceptance criteria: all 22 met
  1. User model with correct columns: MET
  2. Alembic migration: MET
  3. passlib + python-jose in pyproject.toml: MET
  4. Settings with secret_key, expire config: MET
  5. hash_password / verify_password: MET (bcrypt direct, acceptable for Python 3.13)
  6. create_access_token with sub + type=access: MET
  7. create_refresh_token with sub + type=refresh: MET
  8. decode_token validates and raises on invalid/expired: MET
  9. POST /api/auth/register 201 with tokens: MET
  10. Register duplicate email 409: MET
  11. Register duplicate username 409: MET
  12. POST /api/auth/login 200 with tokens: MET
  13. Login wrong password 401: MET
  14. Login nonexistent email 401: MET
  15. POST /api/auth/refresh 200 with new tokens: MET
  16. Refresh with invalid/expired token 401: MET
  17. GET /api/auth/me 200 with user info: MET
  18. GET /api/auth/me without auth 401: MET
  19. GET /api/auth/me with expired token 401: MET
  20. Protected endpoints 401 without token: MET
  21. GET /api/health still accessible: MET
  22. Passwords never in plaintext: MET
- Code quality: clean, well-structured, follows project patterns, no over-engineering
- Tests are meaningful: 26 tests covering unit (password, JWT) and integration (all 4 endpoints + route protection)
- All existing tests updated consistently for auth compatibility
- Follow-up issues created: none needed
- VERDICT: ACCEPT
