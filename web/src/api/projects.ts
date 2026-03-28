import { apiClient } from "./client";

export interface ProjectRead {
  id: string;
  name: string;
  path: string;
  description: string | null;
  archetype: string | null;
  knowledge: string | null;
  created_at: string;
  archived_at: string | null;
}

export async function fetchProjects(): Promise<ProjectRead[]> {
  const response = await apiClient.get("/api/projects");
  if (!response.ok) {
    throw new Error(`Failed to fetch projects: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead[]>;
}

export async function fetchArchivedProjects(): Promise<ProjectRead[]> {
  const response = await apiClient.get("/api/projects/archived");
  if (!response.ok) {
    throw new Error(`Failed to fetch archived projects: ${response.status}`);
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

export async function archiveProject(id: string): Promise<ProjectRead> {
  const response = await apiClient.post(`/api/projects/${id}/archive`, {});
  if (!response.ok) {
    throw new Error(`Failed to archive project: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead>;
}

export async function unarchiveProject(id: string): Promise<ProjectRead> {
  const response = await apiClient.post(`/api/projects/${id}/unarchive`, {});
  if (!response.ok) {
    throw new Error(`Failed to unarchive project: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead>;
}

export async function deleteProject(id: string): Promise<void> {
  const response = await apiClient.delete(`/api/projects/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to delete project: ${response.status}`);
  }
}
