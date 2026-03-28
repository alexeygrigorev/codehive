import { apiClient } from "./client";

export interface PromptTemplate {
  role: string;
  display_name: string;
  system_prompt: string;
  is_custom: boolean;
}

export interface EngineConfig {
  engine: string;
  extra_args: string[];
}

export async function fetchPromptTemplates(
  projectId: string,
): Promise<PromptTemplate[]> {
  const resp = await apiClient.get(
    `/api/projects/${projectId}/prompt-templates`,
  );
  if (!resp.ok) throw new Error(`Failed to fetch prompt templates: ${resp.status}`);
  return resp.json() as Promise<PromptTemplate[]>;
}

export async function updatePromptTemplate(
  projectId: string,
  role: string,
  systemPrompt: string,
): Promise<PromptTemplate> {
  const resp = await apiClient.put(
    `/api/projects/${projectId}/prompt-templates/${role}`,
    { system_prompt: systemPrompt },
  );
  if (!resp.ok) throw new Error(`Failed to update prompt template: ${resp.status}`);
  return resp.json() as Promise<PromptTemplate>;
}

export async function resetPromptTemplate(
  projectId: string,
  role: string,
): Promise<PromptTemplate> {
  const resp = await apiClient.delete(
    `/api/projects/${projectId}/prompt-templates/${role}`,
  );
  if (!resp.ok) throw new Error(`Failed to reset prompt template: ${resp.status}`);
  return resp.json() as Promise<PromptTemplate>;
}

export async function fetchEngineConfig(
  projectId: string,
): Promise<EngineConfig[]> {
  const resp = await apiClient.get(
    `/api/projects/${projectId}/engine-config`,
  );
  if (!resp.ok) throw new Error(`Failed to fetch engine config: ${resp.status}`);
  return resp.json() as Promise<EngineConfig[]>;
}

export async function updateEngineConfig(
  projectId: string,
  engine: string,
  extraArgs: string[],
): Promise<EngineConfig> {
  const resp = await apiClient.put(
    `/api/projects/${projectId}/engine-config/${engine}`,
    { extra_args: extraArgs },
  );
  if (!resp.ok) throw new Error(`Failed to update engine config: ${resp.status}`);
  return resp.json() as Promise<EngineConfig>;
}
