import { apiClient } from "./client";

export interface ProjectRead {
  id: string;
  name: string;
  path: string;
  description: string | null;
  archetype: string | null;
  knowledge: string | null;
  created_at: string;
}

export async function fetchProjects(): Promise<ProjectRead[]> {
  const response = await apiClient.get("/api/projects");
  if (!response.ok) {
    throw new Error(`Failed to fetch projects: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead[]>;
}

export async function createProject(body: {
  name: string;
  path?: string;
  description?: string;
  git_init?: boolean;
}): Promise<ProjectRead> {
  const response = await apiClient.post("/api/projects", body);
  if (!response.ok) {
    throw new Error(`Failed to create project: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead>;
}

export async function fetchProject(id: string): Promise<ProjectRead> {
  const response = await apiClient.get(`/api/projects/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch project: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead>;
}
