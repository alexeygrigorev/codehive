const baseURL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface ApiClient {
  baseURL: string;
  get: (path: string) => Promise<Response>;
  post: (path: string, body: unknown) => Promise<Response>;
}

export const apiClient: ApiClient = {
  baseURL,
  get(path: string): Promise<Response> {
    return fetch(`${this.baseURL}${path}`);
  },
  post(path: string, body: unknown): Promise<Response> {
    return fetch(`${this.baseURL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
