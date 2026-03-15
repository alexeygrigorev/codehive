import { apiClient } from "./client";

export interface ReplayStep {
  index: number;
  timestamp: string;
  step_type: string;
  data: Record<string, unknown>;
}

export interface ReplayResponse {
  session_id: string;
  session_status: string;
  total_steps: number;
  steps: ReplayStep[];
}

export async function fetchReplay(
  sessionId: string,
  limit = 50,
  offset = 0,
): Promise<ReplayResponse> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/replay?limit=${limit}&offset=${offset}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch replay: ${response.status}`);
  }
  return response.json() as Promise<ReplayResponse>;
}
