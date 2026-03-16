import { apiClient } from "./client";

export interface FlowQuestion {
  id: string;
  text: string;
  category: string;
}

export interface FlowAnswer {
  question_id: string;
  answer: string;
}

export interface SuggestedSession {
  name: string;
  mission: string;
  mode: string;
}

export interface ProjectBrief {
  name: string;
  description: string;
  tech_stack: string[];
  architecture: string;
  open_decisions: string[];
  suggested_sessions: SuggestedSession[];
}

export interface FlowStartResult {
  flow_id: string;
  session_id: string;
  first_questions: FlowQuestion[];
}

export interface FlowRespondResult {
  next_questions: FlowQuestion[] | null;
  brief: ProjectBrief | null;
}

export interface FlowFinalizeResult {
  project_id: string;
  sessions: CreatedSession[];
}

export interface CreatedSession {
  id: string;
  name: string;
  mode: string;
}

export async function startFlow(body: {
  flow_type: string;
  initial_input?: string;
  workspace_id?: string;
}): Promise<FlowStartResult> {
  const response = await apiClient.post("/api/project-flow/start", body);
  if (!response.ok) {
    throw new Error(`Failed to start flow: ${response.status}`);
  }
  return response.json() as Promise<FlowStartResult>;
}

export async function respondToFlow(
  flowId: string,
  answers: FlowAnswer[],
): Promise<FlowRespondResult> {
  const response = await apiClient.post(
    `/api/project-flow/${flowId}/respond`,
    { answers },
  );
  if (!response.ok) {
    throw new Error(`Failed to respond to flow: ${response.status}`);
  }
  return response.json() as Promise<FlowRespondResult>;
}

export async function finalizeFlow(
  flowId: string,
): Promise<FlowFinalizeResult> {
  const response = await apiClient.post(
    `/api/project-flow/${flowId}/finalize`,
    {},
  );
  if (!response.ok) {
    throw new Error(`Failed to finalize flow: ${response.status}`);
  }
  return response.json() as Promise<FlowFinalizeResult>;
}
