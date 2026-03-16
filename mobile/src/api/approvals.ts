import apiClient from "./client";

export async function listPendingApprovals() {
  const response = await apiClient.get("/api/approvals");
  return response.data;
}

export async function approve(id: string) {
  const response = await apiClient.post(`/api/approvals/${id}/approve`);
  return response.data;
}

export async function reject(id: string) {
  const response = await apiClient.post(`/api/approvals/${id}/reject`);
  return response.data;
}
