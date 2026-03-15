import { apiClient } from "./client";

export interface SessionRead {
  id: string;
  project_id: string;
  issue_id: string | null;
  parent_session_id: string | null;
  name: string;
  engine: string;
  mode: string;
  status: string;
  config: Record<string, unknown> | null;
  created_at: string;
}

export async function fetchSessions(
  projectId: string,
): Promise<SessionRead[]> {
  const response = await apiClient.get(
    `/api/projects/${projectId}/sessions`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch sessions: ${response.status}`);
  }
  return response.json() as Promise<SessionRead[]>;
}
