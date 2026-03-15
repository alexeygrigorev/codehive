import { apiClient } from "./client";

export interface TunnelRead {
  id: string;
  target_id: string;
  remote_port: number;
  local_port: number;
  label: string;
  status: string;
  created_at: string;
}

export interface TunnelCreate {
  target_id: string;
  remote_port: number;
  local_port: number;
  label?: string;
}

export interface TunnelPreviewURL {
  tunnel_id: string;
  url: string;
}

export async function fetchTunnels(
  targetId?: string,
): Promise<TunnelRead[]> {
  const query = targetId ? `?target_id=${targetId}` : "";
  const response = await apiClient.get(`/api/tunnels${query}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch tunnels: ${response.status}`);
  }
  return response.json() as Promise<TunnelRead[]>;
}

export async function createTunnel(
  data: TunnelCreate,
): Promise<TunnelRead> {
  const response = await apiClient.post("/api/tunnels", data);
  if (!response.ok) {
    throw new Error(`Failed to create tunnel: ${response.status}`);
  }
  return response.json() as Promise<TunnelRead>;
}

export async function closeTunnel(tunnelId: string): Promise<void> {
  const response = await apiClient.delete(`/api/tunnels/${tunnelId}`);
  if (!response.ok) {
    throw new Error(`Failed to close tunnel: ${response.status}`);
  }
}

export async function fetchTunnelPreview(
  tunnelId: string,
): Promise<TunnelPreviewURL> {
  const response = await apiClient.get(`/api/tunnels/${tunnelId}/preview`);
  if (!response.ok) {
    throw new Error(`Failed to fetch preview URL: ${response.status}`);
  }
  return response.json() as Promise<TunnelPreviewURL>;
}
