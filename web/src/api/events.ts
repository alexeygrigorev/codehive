import { apiClient } from "./client";

export interface EventRead {
  id: string;
  session_id: string;
  type: string;
  data: Record<string, unknown>;
  created_at: string;
}

export async function fetchEvents(sessionId: string): Promise<EventRead[]> {
  const response = await apiClient.get(`/api/sessions/${sessionId}/events`);
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`);
  }
  return response.json() as Promise<EventRead[]>;
}

export async function fetchEventsByType(
  sessionId: string,
  type: string,
): Promise<EventRead[]> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/events?type=${encodeURIComponent(type)}&limit=200`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`);
  }
  return response.json() as Promise<EventRead[]>;
}
