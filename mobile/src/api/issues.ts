import apiClient from "./client";

export async function listIssues(projectId: string, status?: string) {
  const params = status ? { params: { status } } : undefined;
  const response = await apiClient.get(
    `/api/projects/${projectId}/issues`,
    params
  );
  return response.data;
}

export async function getIssue(issueId: string) {
  const response = await apiClient.get(`/api/issues/${issueId}`);
  return response.data;
}
