import apiClient from "./client";

export async function listSessions(projectId: string) {
  const response = await apiClient.get(
    `/api/projects/${projectId}/sessions`
  );
  return response.data;
}

export async function getSession(id: string) {
  const response = await apiClient.get(`/api/sessions/${id}`);
  return response.data;
}

export async function sendMessage(id: string, text: string) {
  const response = await apiClient.post(`/api/sessions/${id}/messages`, {
    content: text,
  });
  return response.data;
}
