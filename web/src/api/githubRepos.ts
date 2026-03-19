import { apiClient } from "./client";

export interface GhStatusResponse {
  available: boolean;
  authenticated: boolean;
  username: string | null;
  error: string | null;
}

export interface RepoItem {
  name: string;
  full_name: string;
  description: string | null;
  language: string | null;
  updated_at: string | null;
  is_private: boolean;
  clone_url: string;
}

export interface RepoListResponse {
  repos: RepoItem[];
  owner: string | null;
  total: number;
}

export interface CloneRequest {
  repo_url: string;
  destination: string;
  project_name: string;
}

export interface CloneResponse {
  project_id: string;
  project_name: string;
  path: string;
  cloned: boolean;
}

export async function fetchGhStatus(): Promise<GhStatusResponse> {
  const response = await apiClient.get("/api/github/status");
  if (!response.ok) {
    throw new Error(`Failed to fetch GitHub status: ${response.status}`);
  }
  return response.json() as Promise<GhStatusResponse>;
}

export async function fetchGhRepos(params?: {
  owner?: string;
  search?: string;
  limit?: number;
}): Promise<RepoListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.owner) searchParams.set("owner", params.owner);
  if (params?.search) searchParams.set("search", params.search);
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const qs = searchParams.toString();
  const url = `/api/github/repos${qs ? `?${qs}` : ""}`;

  const response = await apiClient.get(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch repos: ${response.status}`);
  }
  return response.json() as Promise<RepoListResponse>;
}

export async function cloneRepo(
  body: CloneRequest,
): Promise<CloneResponse> {
  const response = await apiClient.post("/api/github/clone", body);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: string }).detail
        : `Clone failed: ${response.status}`;
    throw new Error(detail);
  }
  return response.json() as Promise<CloneResponse>;
}
