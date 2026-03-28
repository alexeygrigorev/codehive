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
  role: string | null;
  config: Record<string, unknown> | null;
  created_at: string;
  agent_profile_id: string | null;
  agent_name: string | null;
  agent_avatar_url: string | null;
}

export async function createSession(
  projectId: string,
  body: {
    name: string;
    engine?: string;
    mode?: string;
    issue_id?: string;
    config?: Record<string, unknown>;
  },
): Promise<SessionRead> {
  const response = await apiClient.post(
    `/api/projects/${projectId}/sessions`,
    {
      engine: "claude_code",
      mode: "execution",
      ...body,
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status}`);
  }
  return response.json() as Promise<SessionRead>;
}

export async function updateSession(
  sessionId: string,
  body: { name?: string; mode?: string; config?: Record<string, unknown> },
): Promise<SessionRead> {
  const response = await apiClient.patch(`/api/sessions/${sessionId}`, body);
  if (!response.ok) {
    throw new Error(`Failed to update session: ${response.status}`);
  }
  return response.json() as Promise<SessionRead>;
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

export async function deleteSession(
  sessionId: string,
): Promise<void> {
  const response = await apiClient.delete(`/api/sessions/${sessionId}`);
  if (!response.ok) {
    if (response.status === 409) {
      throw new Error(
        "Cannot delete this session because it has sub-agent sessions. Delete those first.",
      );
    }
    throw new Error(`Failed to delete session: ${response.status}`);
  }
}
