import { apiClient } from "./client";

export interface CheckpointRead {
  id: string;
  session_id: string;
  label: string | null;
  git_ref: string | null;
  created_at: string;
}

export async function fetchCheckpoints(
  sessionId: string,
): Promise<CheckpointRead[]> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/checkpoints`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch checkpoints: ${response.status}`);
  }
  return response.json() as Promise<CheckpointRead[]>;
}

export async function createCheckpoint(
  sessionId: string,
  label?: string,
): Promise<CheckpointRead> {
  const response = await apiClient.post(
    `/api/sessions/${sessionId}/checkpoints`,
    label ? { label } : {},
  );
  if (!response.ok) {
    throw new Error(`Failed to create checkpoint: ${response.status}`);
  }
  return response.json() as Promise<CheckpointRead>;
}

export async function rollbackCheckpoint(
  checkpointId: string,
): Promise<void> {
  const response = await apiClient.post(
    `/api/checkpoints/${checkpointId}/rollback`,
    {},
  );
  if (!response.ok) {
    throw new Error(`Failed to rollback checkpoint: ${response.status}`);
  }
}
