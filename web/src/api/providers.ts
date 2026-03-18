import { apiClient } from "./client";

export interface ProviderInfo {
  name: string;
  base_url: string;
  api_key_set: boolean;
  default_model: string;
}

export async function fetchProviders(): Promise<ProviderInfo[]> {
  const response = await apiClient.get("/api/providers");
  if (!response.ok) {
    throw new Error(`Failed to fetch providers: ${response.status}`);
  }
  return response.json() as Promise<ProviderInfo[]>;
}
