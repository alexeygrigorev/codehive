import apiClient from "./client";

export interface SearchFilters {
  type?: "session" | "message" | "issue" | "event";
  project_id?: string;
  limit?: number;
  offset?: number;
}

export interface SearchResult {
  type: "session" | "message" | "issue" | "event";
  id: string;
  snippet: string;
  score: number;
  created_at: string;
  project_id?: string;
  session_id?: string;
  project_name?: string;
  session_name?: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  has_more: boolean;
}

export async function searchAll(
  query: string,
  filters?: SearchFilters,
): Promise<SearchResponse> {
  const params: Record<string, string | number> = { q: query };
  if (filters?.type) {
    params.type = filters.type;
  }
  if (filters?.project_id) {
    params.project_id = filters.project_id;
  }
  if (filters?.limit !== undefined) {
    params.limit = filters.limit;
  }
  if (filters?.offset !== undefined) {
    params.offset = filters.offset;
  }
  const response = await apiClient.get("/api/search", { params });
  return response.data;
}
