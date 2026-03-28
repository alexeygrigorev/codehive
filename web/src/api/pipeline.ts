import { apiClient } from "./client";

export interface PipelineTask {
  id: string;
  session_id: string;
  title: string;
  instructions: string | null;
  status: string;
  pipeline_status: string;
  priority: number;
  depends_on: string | null;
  mode: string;
  created_by: string;
  created_at: string;
  issue_id: string | null;
}

export interface PipelineLogEntry {
  id: string;
  task_id: string;
  from_status: string;
  to_status: string;
  actor: string | null;
  created_at: string;
}

export interface OrchestratorStatus {
  status: string;
  project_id: string | null;
  current_batch: string[] | null;
  active_sessions: string[] | null;
  flagged_tasks: string[] | null;
}

export interface AddTaskPayload {
  project_id: string;
  title: string;
  description?: string;
  acceptance_criteria?: string;
}

export interface AddTaskResult {
  issue_id: string;
  task_id: string;
  pipeline_status: string;
}

export async function fetchSessionTasks(
  sessionId: string,
  pipelineStatus?: string,
): Promise<PipelineTask[]> {
  const query = pipelineStatus ? `?pipeline_status=${pipelineStatus}` : "";
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/tasks${query}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch tasks: ${response.status}`);
  }
  return response.json() as Promise<PipelineTask[]>;
}

export async function fetchTaskPipelineLog(
  taskId: string,
): Promise<PipelineLogEntry[]> {
  const response = await apiClient.get(`/api/tasks/${taskId}/pipeline-log`);
  if (!response.ok) {
    throw new Error(`Failed to fetch pipeline log: ${response.status}`);
  }
  return response.json() as Promise<PipelineLogEntry[]>;
}

export async function fetchOrchestratorStatus(
  projectId: string,
): Promise<OrchestratorStatus> {
  const response = await apiClient.get(
    `/api/orchestrator/status?project_id=${projectId}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch orchestrator status: ${response.status}`);
  }
  return response.json() as Promise<OrchestratorStatus>;
}

export interface IssueLogEntry {
  id: string;
  issue_id: string;
  agent_role: string;
  agent_profile_id: string | null;
  agent_name: string | null;
  agent_avatar_url: string | null;
  content: string;
  created_at: string;
}

export async function fetchIssueLogEntries(
  issueId: string,
): Promise<IssueLogEntry[]> {
  const response = await apiClient.get(`/api/issues/${issueId}/logs`);
  if (!response.ok) {
    throw new Error(`Failed to fetch issue logs: ${response.status}`);
  }
  return response.json() as Promise<IssueLogEntry[]>;
}

export async function addTask(
  payload: AddTaskPayload,
): Promise<AddTaskResult> {
  const response = await apiClient.post("/api/orchestrator/add-task", payload);
  if (!response.ok) {
    throw new Error(`Failed to add task: ${response.status}`);
  }
  return response.json() as Promise<AddTaskResult>;
}
