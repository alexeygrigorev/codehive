import { apiClient } from "./client";

export interface TaskRead {
  id: string;
  session_id: string;
  title: string;
  instructions: string;
  status: string;
  priority: number;
  depends_on: string[];
  mode: string;
  created_by: string;
  created_at: string;
}

export async function fetchTasks(sessionId: string): Promise<TaskRead[]> {
  const response = await apiClient.get(`/api/sessions/${sessionId}/tasks`);
  if (!response.ok) {
    throw new Error(`Failed to fetch tasks: ${response.status}`);
  }
  return response.json() as Promise<TaskRead[]>;
}
