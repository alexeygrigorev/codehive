# 59c: Login UI + Auth Flow

## Description
Frontend login/register pages, token storage, authenticated API requests, and protected routes.

## Implementation Plan

### 1. Auth pages
- `web/src/pages/LoginPage.tsx` -- email + password form, "Login" button, link to register
- `web/src/pages/RegisterPage.tsx` -- email + username + password + confirm password form
- Route: `/login`, `/register`

### 2. Auth context
- `web/src/context/AuthContext.tsx`
- Stores: `user`, `accessToken`, `refreshToken`, `isAuthenticated`, `isLoading`
- `login(email, password)` -- calls `/api/auth/login`, stores tokens
- `register(email, username, password)` -- calls `/api/auth/register`, stores tokens
- `logout()` -- clears tokens, redirects to `/login`
- `refreshAccessToken()` -- calls `/api/auth/refresh`
- Tokens stored in `localStorage`

### 3. API client integration
- Update `web/src/api/client.ts` (axios instance):
  - Add auth token interceptor: attach `Authorization: Bearer {token}` to all requests
  - Add response interceptor: on 401, attempt token refresh; if refresh fails, logout
  - Retry the original request after successful refresh

### 4. Protected routes
- `web/src/components/ProtectedRoute.tsx` -- wrapper that redirects to `/login` if not authenticated
- Wrap all existing routes except `/login` and `/register`
- Show loading spinner while checking auth state on initial load

### 5. User menu
- `web/src/components/UserMenu.tsx` -- shows username/email, logout button
- Displayed in the app header/navbar
- Dropdown: "Profile", "Settings", "Logout"

## Acceptance Criteria

- [ ] `/login` page renders with email + password form
- [ ] `/register` page renders with email + username + password + confirm password form
- [ ] Successful login stores tokens and redirects to dashboard
- [ ] Successful registration stores tokens and redirects to dashboard
- [ ] Invalid credentials show error message on login page
- [ ] All pages except `/login` and `/register` redirect to `/login` when not authenticated
- [ ] API requests include auth token in Authorization header
- [ ] Expired token triggers automatic refresh; if refresh fails, user is logged out
- [ ] User menu in header shows username and logout option
- [ ] Logout clears tokens and redirects to `/login`

## Test Scenarios

### Unit: LoginPage
- Render, verify email and password inputs present
- Submit with valid credentials (mock API), verify redirect to dashboard
- Submit with invalid credentials, verify error message shown

### Unit: RegisterPage
- Render, verify all form fields present
- Submit with mismatched passwords, verify client-side validation error
- Submit with valid data, verify API call and redirect

### Unit: AuthContext
- Set tokens, verify isAuthenticated is true
- Clear tokens, verify isAuthenticated is false
- Mock expired token response, verify refresh is attempted

### Unit: ProtectedRoute
- Render without auth, verify redirect to /login
- Render with auth, verify children are rendered

### Integration: Auth flow
- Register, verify dashboard loads
- Refresh page, verify still authenticated (tokens in localStorage)
- Logout, verify redirect to login

## Dependencies
- Depends on: #59a (auth API endpoints), #14 (React app)
