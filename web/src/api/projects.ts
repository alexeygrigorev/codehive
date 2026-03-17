import { apiClient } from "./client";

export interface ProjectRead {
  id: string;
  workspace_id: string;
  name: string;
  path: string;
  description: string | null;
  archetype: string | null;
  knowledge: string | null;
  created_at: string;
}

export async function fetchDefaultWorkspaceId(): Promise<string> {
  const response = await apiClient.get("/api/workspaces");
  if (!response.ok) {
    throw new Error(`Failed to fetch workspaces: ${response.status}`);
  }
  const workspaces = (await response.json()) as { id: string }[];
  if (workspaces.length === 0) {
    throw new Error("No workspaces found");
  }
  return workspaces[0].id;
}

export async function fetchProjects(): Promise<ProjectRead[]> {
  const response = await apiClient.get("/api/projects");
  if (!response.ok) {
    throw new Error(`Failed to fetch projects: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead[]>;
}

export async function createProject(body: {
  workspace_id: string;
  name: string;
  description?: string;
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
