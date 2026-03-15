import { apiClient } from "./client";

export async function approveAction(
  sessionId: string,
  actionId: string,
): Promise<void> {
  const response = await apiClient.post(
    `/api/sessions/${sessionId}/approve`,
    { action_id: actionId },
  );
  if (!response.ok) {
    throw new Error(`Failed to approve action: ${response.status}`);
  }
}

export async function rejectAction(
  sessionId: string,
  actionId: string,
): Promise<void> {
  const response = await apiClient.post(
    `/api/sessions/${sessionId}/reject`,
    { action_id: actionId },
  );
  if (!response.ok) {
    throw new Error(`Failed to reject action: ${response.status}`);
  }
}
