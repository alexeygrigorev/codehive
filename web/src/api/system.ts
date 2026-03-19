import { apiClient } from "./client";

export interface DefaultDirectoryResponse {
  default_directory: string;
}

export interface DirectoryEntry {
  name: string;
  path: string;
  has_git: boolean;
}

export interface DirectoryListResponse {
  path: string;
  parent: string | null;
  directories: DirectoryEntry[];
}

export async function fetchDefaultDirectory(): Promise<DefaultDirectoryResponse> {
  const response = await apiClient.get("/api/system/default-directory");
  if (!response.ok) {
    throw new Error(`Failed to fetch default directory: ${response.status}`);
  }
  return response.json() as Promise<DefaultDirectoryResponse>;
}

export async function fetchDirectories(
  path: string,
): Promise<DirectoryListResponse> {
  const response = await apiClient.get(
    `/api/system/directories?path=${encodeURIComponent(path)}`,
  );
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error("Path is outside the home directory");
    }
    if (response.status === 404) {
      throw new Error("Directory not found");
    }
    throw new Error(`Failed to list directories: ${response.status}`);
  }
  return response.json() as Promise<DirectoryListResponse>;
}
