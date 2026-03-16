const baseURL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:7433";

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserRead {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export async function loginUser(
  email: string,
  password: string,
): Promise<AuthTokens> {
  const response = await fetch(`${baseURL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Login failed: ${response.status}`);
  }
  return response.json() as Promise<AuthTokens>;
}

export async function registerUser(
  email: string,
  username: string,
  password: string,
): Promise<AuthTokens> {
  const response = await fetch(`${baseURL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username, password }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Registration failed: ${response.status}`);
  }
  return response.json() as Promise<AuthTokens>;
}

export async function refreshToken(
  refresh_token: string,
): Promise<AuthTokens> {
  const response = await fetch(`${baseURL}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (!response.ok) {
    throw new Error(`Token refresh failed: ${response.status}`);
  }
  return response.json() as Promise<AuthTokens>;
}

export async function getMe(accessToken: string): Promise<UserRead> {
  const response = await fetch(`${baseURL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch user: ${response.status}`);
  }
  return response.json() as Promise<UserRead>;
}
