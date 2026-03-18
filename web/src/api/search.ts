import { apiClient } from "./client";

export type EntityType = "session" | "message" | "issue" | "event";

export interface SearchResultItem {
  type: EntityType;
  id: string;
  snippet: string;
  score: number;
  created_at: string;
  project_id: string | null;
  session_id: string | null;
  project_name: string | null;
  session_name: string | null;
}

export interface SearchResponse {
  results: SearchResultItem[];
  total: number;
  has_more: boolean;
}

export interface SearchFilters {
  type?: EntityType;
  project_id?: string;
  limit?: number;
  offset?: number;
}

export interface SessionHistoryItem {
  type: string;
  id: string;
  snippet: string;
  score: number;
  created_at: string;
}

export interface SessionHistoryResponse {
  results: SessionHistoryItem[];
  total: number;
  has_more: boolean;
}

export async function searchAll(
  query: string,
  filters?: SearchFilters,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (filters?.type) params.set("type", filters.type);
  if (filters?.project_id) params.set("project_id", filters.project_id);
  if (filters?.limit !== undefined) params.set("limit", String(filters.limit));
  if (filters?.offset !== undefined)
    params.set("offset", String(filters.offset));

  const response = await apiClient.get(`/api/search?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }
  return response.json() as Promise<SearchResponse>;
}

export async function searchSessionHistory(
  sessionId: string,
  query: string,
): Promise<SessionHistoryResponse> {
  const params = new URLSearchParams({ q: query });
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/history?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Session history search failed: ${response.status}`);
  }
  return response.json() as Promise<SessionHistoryResponse>;
}
