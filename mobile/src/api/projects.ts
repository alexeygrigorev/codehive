import apiClient from "./client";

export async function listProjects() {
  const response = await apiClient.get("/api/projects");
  return response.data;
}

export async function getProject(id: string) {
  const response = await apiClient.get(`/api/projects/${id}`);
  return response.data;
}
