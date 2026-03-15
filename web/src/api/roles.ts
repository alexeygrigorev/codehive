import { apiClient } from "./client";

export interface RoleRead {
  name: string;
  display_name: string;
  description: string;
  is_builtin: boolean;
  responsibilities: string[];
  allowed_tools: string[];
  denied_tools: string[];
  coding_rules: string[];
  system_prompt_extra: string;
}

export interface RoleCreate {
  name: string;
  display_name: string;
  description: string;
  responsibilities?: string[];
  allowed_tools?: string[];
  denied_tools?: string[];
  coding_rules?: string[];
  system_prompt_extra?: string;
}

export interface RoleUpdate {
  display_name?: string;
  description?: string;
  responsibilities?: string[];
  allowed_tools?: string[];
  denied_tools?: string[];
  coding_rules?: string[];
  system_prompt_extra?: string;
}

export async function fetchRoles(): Promise<RoleRead[]> {
  const response = await apiClient.get("/api/roles");
  if (!response.ok) {
    throw new Error(`Failed to fetch roles: ${response.status}`);
  }
  return response.json() as Promise<RoleRead[]>;
}

export async function fetchRole(roleName: string): Promise<RoleRead> {
  const response = await apiClient.get(`/api/roles/${roleName}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch role: ${response.status}`);
  }
  return response.json() as Promise<RoleRead>;
}

export async function createRole(body: RoleCreate): Promise<RoleRead> {
  const response = await apiClient.post("/api/roles", body);
  if (!response.ok) {
    throw new Error(`Failed to create role: ${response.status}`);
  }
  return response.json() as Promise<RoleRead>;
}

export async function updateRole(
  roleName: string,
  body: RoleUpdate,
): Promise<RoleRead> {
  const response = await apiClient.put(`/api/roles/${roleName}`, body);
  if (!response.ok) {
    throw new Error(`Failed to update role: ${response.status}`);
  }
  return response.json() as Promise<RoleRead>;
}

export async function deleteRole(roleName: string): Promise<void> {
  const response = await apiClient.delete(`/api/roles/${roleName}`);
  if (!response.ok) {
    throw new Error(`Failed to delete role: ${response.status}`);
  }
}
