import { apiClient } from "./client";

export interface ContextFileEntry {
  path: string;
  size: number;
}

export interface ContextFileContent {
  path: string;
  content: string;
}

export async function fetchContextFiles(
  projectId: string,
): Promise<ContextFileEntry[]> {
  const response = await apiClient.get(
    `/api/projects/${projectId}/context-files`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch context files: ${response.status}`);
  }
  return response.json() as Promise<ContextFileEntry[]>;
}

export async function fetchContextFileContent(
  projectId: string,
  filePath: string,
): Promise<ContextFileContent> {
  const response = await apiClient.get(
    `/api/projects/${projectId}/context-files/${filePath}`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch context file: ${response.status}`);
  }
  return response.json() as Promise<ContextFileContent>;
}
