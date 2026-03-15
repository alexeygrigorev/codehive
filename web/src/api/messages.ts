import { apiClient } from "./client";
import type { SessionEvent } from "./websocket";

export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<SessionEvent[]> {
  const response = await apiClient.post(
    `/api/sessions/${sessionId}/messages`,
    { content },
  );
  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.status}`);
  }
  return response.json() as Promise<SessionEvent[]>;
}

export async function fetchMessages(
  sessionId: string,
): Promise<SessionEvent[]> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/messages`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch messages: ${response.status}`);
  }
  return response.json() as Promise<SessionEvent[]>;
}
