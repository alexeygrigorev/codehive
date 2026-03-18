import { apiClient } from "./client";

export interface ProviderInfo {
  name: string;
  type: string;
  available: boolean;
  reason: string;
  default_model: string;
}

export async function fetchProviders(): Promise<ProviderInfo[]> {
  const response = await apiClient.get("/api/providers");
  if (!response.ok) {
    throw new Error(`Failed to fetch providers: ${response.status}`);
  }
  return response.json() as Promise<ProviderInfo[]>;
}
