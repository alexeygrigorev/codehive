import { apiClient } from "./client";
import type { EventRead } from "./events";

export interface AgentCommEvent {
  id: string;
  session_id: string;
  type: "agent.message" | "agent.query";
  data: {
    sender_session_id: string;
    target_session_id: string;
    message: string;
    timestamp: string;
    [key: string]: unknown;
  };
  created_at: string;
}

const AGENT_COMM_TYPES = new Set(["agent.message", "agent.query"]);

export async function fetchAgentMessages(
  sessionId: string,
): Promise<AgentCommEvent[]> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/events`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch agent messages: ${response.status}`);
  }
  const events = (await response.json()) as EventRead[];
  return events.filter((e) =>
    AGENT_COMM_TYPES.has(e.type),
  ) as unknown as AgentCommEvent[];
}
