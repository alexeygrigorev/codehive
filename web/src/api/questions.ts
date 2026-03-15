import { apiClient } from "./client";

export interface QuestionRead {
  id: string;
  session_id: string;
  question: string;
  context: string | null;
  answered: boolean;
  answer: string | null;
  created_at: string;
}

export async function fetchAllQuestions(
  answered?: boolean,
): Promise<QuestionRead[]> {
  const params = new URLSearchParams();
  if (answered !== undefined) {
    params.set("answered", String(answered));
  }
  const query = params.toString();
  const path = `/api/questions${query ? `?${query}` : ""}`;
  const response = await apiClient.get(path);
  if (!response.ok) {
    throw new Error(`Failed to fetch questions: ${response.status}`);
  }
  return response.json() as Promise<QuestionRead[]>;
}

export async function fetchSessionQuestions(
  sessionId: string,
  answered?: boolean,
): Promise<QuestionRead[]> {
  const params = new URLSearchParams();
  if (answered !== undefined) {
    params.set("answered", String(answered));
  }
  const query = params.toString();
  const path = `/api/sessions/${sessionId}/questions${query ? `?${query}` : ""}`;
  const response = await apiClient.get(path);
  if (!response.ok) {
    throw new Error(`Failed to fetch session questions: ${response.status}`);
  }
  return response.json() as Promise<QuestionRead[]>;
}

export async function answerQuestion(
  sessionId: string,
  questionId: string,
  answer: string,
): Promise<QuestionRead> {
  const response = await apiClient.post(
    `/api/sessions/${sessionId}/questions/${questionId}/answer`,
    { answer },
  );
  if (!response.ok) {
    throw new Error(`Failed to answer question: ${response.status}`);
  }
  return response.json() as Promise<QuestionRead>;
}
