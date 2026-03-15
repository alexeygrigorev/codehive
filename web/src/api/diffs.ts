import { apiClient } from "./client";

export interface DiffFileEntry {
  path: string;
  diff_text: string;
  additions: number;
  deletions: number;
}

export interface SessionDiffsResponse {
  session_id: string;
  files: DiffFileEntry[];
}

export async function fetchSessionDiffs(
  sessionId: string,
): Promise<SessionDiffsResponse> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/diffs`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch session diffs: ${response.status}`);
  }
  return response.json() as Promise<SessionDiffsResponse>;
}
