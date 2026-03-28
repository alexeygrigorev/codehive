import { apiClient } from "./client";

export interface AgentProfileRead {
  id: string;
  project_id: string;
  name: string;
  role: string;
  avatar_seed: string;
  avatar_url: string;
  personality: string | null;
  system_prompt_modifier: string | null;
  preferred_engine: string | null;
  preferred_model: string | null;
  created_at: string;
}

export async function fetchTeam(
  projectId: string,
): Promise<AgentProfileRead[]> {
  const response = await apiClient.get(
    `/api/projects/${projectId}/team`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch team: ${response.status}`);
  }
  return response.json() as Promise<AgentProfileRead[]>;
}

export async function generateTeam(
  projectId: string,
): Promise<AgentProfileRead[]> {
  const response = await apiClient.post(
    `/api/projects/${projectId}/team/generate`,
    {},
  );
  if (response.status === 409) {
    throw new Error("Team already exists");
  }
  if (!response.ok) {
    throw new Error(`Failed to generate team: ${response.status}`);
  }
  return response.json() as Promise<AgentProfileRead[]>;
}
