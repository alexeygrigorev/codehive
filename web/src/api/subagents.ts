import { apiClient } from "./client";
import type { SessionRead } from "./sessions";

export async function fetchSubAgents(
  sessionId: string,
): Promise<SessionRead[]> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/subagents`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch sub-agents: ${response.status}`);
  }
  return response.json() as Promise<SessionRead[]>;
}
