const baseURL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:7433";

async function request(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const url = `${baseURL}${path}`;

  if (init) {
    return fetch(url, init);
  }
  return fetch(url);
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
