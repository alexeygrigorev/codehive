import { apiClient } from "./client";

export interface IssueRead {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: string;
  created_at: string;
}

export type IssueStatus = "open" | "in_progress" | "closed";

export async function fetchIssues(
  projectId: string,
  status?: IssueStatus,
): Promise<IssueRead[]> {
  const query = status ? `?status=${status}` : "";
  const response = await apiClient.get(
    `/api/projects/${projectId}/issues${query}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch issues: ${response.status}`);
  }
  return response.json() as Promise<IssueRead[]>;
}

export async function createIssue(
  projectId: string,
  body: { title: string; description?: string },
): Promise<IssueRead> {
  const response = await apiClient.post(
    `/api/projects/${projectId}/issues`,
    body,
  );
  if (!response.ok) {
    throw new Error(`Failed to create issue: ${response.status}`);
  }
  return response.json() as Promise<IssueRead>;
}
