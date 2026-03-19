import { apiClient } from "./client";

export interface UsageRecordRead {
  id: string;
  session_id: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  created_at: string;
}

export interface UsageSummary {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  estimated_cost: number;
}

export interface UsageResponse {
  records: UsageRecordRead[];
  summary: UsageSummary;
}

export interface UsageParams {
  session_id?: string;
  project_id?: string;
  start_date?: string;
  end_date?: string;
}

function buildQueryString(params: UsageParams): string {
  const parts: string[] = [];
  if (params.session_id) parts.push(`session_id=${params.session_id}`);
  if (params.project_id) parts.push(`project_id=${params.project_id}`);
  if (params.start_date) parts.push(`start_date=${params.start_date}`);
  if (params.end_date) parts.push(`end_date=${params.end_date}`);
  return parts.length > 0 ? `?${parts.join("&")}` : "";
}

export async function fetchUsage(params: UsageParams = {}): Promise<UsageResponse> {
  const qs = buildQueryString(params);
  const response = await apiClient.get(`/api/usage${qs}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch usage: ${response.status}`);
  }
  return response.json() as Promise<UsageResponse>;
}

export async function fetchUsageSummary(params: UsageParams = {}): Promise<UsageSummary> {
  const qs = buildQueryString(params);
  const response = await apiClient.get(`/api/usage/summary${qs}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch usage summary: ${response.status}`);
  }
  return response.json() as Promise<UsageSummary>;
}

export async function fetchSessionUsage(sessionId: string): Promise<UsageSummary> {
  const response = await apiClient.get(`/api/sessions/${sessionId}/usage`);
  if (!response.ok) {
    throw new Error(`Failed to fetch session usage: ${response.status}`);
  }
  return response.json() as Promise<UsageSummary>;
}

export interface ContextUsage {
  used_tokens: number;
  context_window: number;
  usage_percent: number;
  model: string;
  estimated: boolean;
}

export async function fetchSessionContext(sessionId: string): Promise<ContextUsage> {
  const response = await apiClient.get(`/api/sessions/${sessionId}/context`);
  if (!response.ok) {
    throw new Error(`Failed to fetch session context: ${response.status}`);
  }
  return response.json() as Promise<ContextUsage>;
}

export interface RateLimitRead {
  rate_limit_type: string;
  utilization: number;
  resets_at: number;
  is_using_overage: boolean;
  surpassed_threshold: number | null;
  captured_at: string;
}

export interface ModelUsageRead {
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  cost_usd: number;
  context_window: number | null;
  captured_at: string;
}

export interface UsageLimitsResponse {
  rate_limits: RateLimitRead[];
  model_usage: ModelUsageRead[];
}

export async function fetchUsageLimits(): Promise<UsageLimitsResponse> {
  const response = await apiClient.get("/api/usage/limits");
  if (!response.ok) {
    throw new Error(`Failed to fetch usage limits: ${response.status}`);
  }
  return response.json() as Promise<UsageLimitsResponse>;
}
