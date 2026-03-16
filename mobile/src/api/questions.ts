import apiClient from "./client";

export async function listQuestions() {
  const response = await apiClient.get("/api/questions");
  return response.data;
}

export async function answerQuestion(id: string, answer: string) {
  const response = await apiClient.post(`/api/questions/${id}/answer`, {
    answer,
  });
  return response.data;
}
