const baseURL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:7433";

const ACCESS_TOKEN_KEY = "codehive_access_token";
const REFRESH_TOKEN_KEY = "codehive_refresh_token";
const AUTH_DISABLED_KEY = "codehive_auth_disabled";

const AUTH_PATHS = [
  "/api/auth/login",
  "/api/auth/register",
  "/api/auth/refresh",
];

function isAuthPath(path: string): boolean {
  return AUTH_PATHS.some((p) => path === p);
}

/** Returns true when the backend has auth disabled. */
export function isAuthDisabled(): boolean {
  return localStorage.getItem(AUTH_DISABLED_KEY) === "true";
}

/** Called by AuthProvider after fetching /api/auth/config. */
export function setAuthDisabled(disabled: boolean): void {
  if (disabled) {
    localStorage.setItem(AUTH_DISABLED_KEY, "true");
  } else {
    localStorage.removeItem(AUTH_DISABLED_KEY);
  }
}

function getAuthHeaders(path: string): Record<string, string> {
  if (isAuthPath(path)) return {};
  if (isAuthDisabled()) return {};
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function handleUnauthorized(
  path: string,
  init: RequestInit,
): Promise<Response | null> {
  if (isAuthPath(path)) return null;

  const refreshTokenValue = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshTokenValue) {
    clearTokensAndRedirect();
    return null;
  }

  try {
    const refreshResponse = await fetch(`${baseURL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshTokenValue }),
    });

    if (!refreshResponse.ok) {
      clearTokensAndRedirect();
      return null;
    }

    const tokens = (await refreshResponse.json()) as {
      access_token: string;
      refresh_token: string;
    };
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);

    // Retry original request with new token
    const retryHeaders = {
      ...((init.headers as Record<string, string>) || {}),
      Authorization: `Bearer ${tokens.access_token}`,
    };
    return fetch(`${baseURL}${path}`, { ...init, headers: retryHeaders });
  } catch {
    clearTokensAndRedirect();
    return null;
  }
}

function clearTokensAndRedirect(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  if (
    typeof window !== "undefined" &&
    window.location.pathname !== "/login"
  ) {
    window.location.href = "/login";
  }
}

async function request(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const authHeaders = getAuthHeaders(path);
  const initHeaders = (init?.headers as Record<string, string>) || {};
  const mergedHeaders = { ...initHeaders, ...authHeaders };
  const hasHeaders = Object.keys(mergedHeaders).length > 0;

  const url = `${baseURL}${path}`;
  let response: Response;

  if (init || hasHeaders) {
    const fetchInit: RequestInit = {
      ...init,
      ...(hasHeaders ? { headers: mergedHeaders } : {}),
    };
    response = await fetch(url, fetchInit);
  } else {
    response = await fetch(url);
  }

  if (response.status === 401 && !isAuthDisabled()) {
    const retryInit: RequestInit = {
      ...init,
      ...(hasHeaders ? { headers: mergedHeaders } : {}),
    };
    const retryResponse = await handleUnauthorized(path, retryInit);
    if (retryResponse) return retryResponse;
  }

  return response;
}

interface ApiClient {
  baseURL: string;
  get: (path: string) => Promise<Response>;
  post: (path: string, body: unknown) => Promise<Response>;
  patch: (path: string, body: unknown) => Promise<Response>;
  put: (path: string, body: unknown) => Promise<Response>;
  delete: (path: string) => Promise<Response>;
}

export const apiClient: ApiClient = {
  baseURL,
  get(path: string): Promise<Response> {
    return request(path);
  },
  post(path: string, body: unknown): Promise<Response> {
    return request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  patch(path: string, body: unknown): Promise<Response> {
    return request(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  put(path: string, body: unknown): Promise<Response> {
    return request(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  delete(path: string): Promise<Response> {
    return request(path, {
      method: "DELETE",
    });
  },
};

export interface HealthCheckResponse {
  status: string;
  [key: string]: unknown;
}

export async function healthCheck(): Promise<HealthCheckResponse> {
  const response = await apiClient.get("/api/health");
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json() as Promise<HealthCheckResponse>;
}
