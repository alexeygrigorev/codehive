import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchAllQuestions,
  fetchSessionQuestions,
  answerQuestion,
} from "@/api/questions";

describe("API: questions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchAllQuestions calls GET /api/questions and returns QuestionRead[]", async () => {
    const mockData = [
      {
        id: "q1",
        session_id: "s1",
        question: "What color?",
        context: null,
        answered: false,
        answer: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchAllQuestions();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/questions",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchAllQuestions(false) calls GET /api/questions?answered=false", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await fetchAllQuestions(false);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/questions?answered=false",
    );
  });

  it("fetchAllQuestions throws on non-200 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchAllQuestions()).rejects.toThrow(
      "Failed to fetch questions: 500",
    );
  });

  it("fetchSessionQuestions(sessionId) calls GET /api/sessions/{sessionId}/questions", async () => {
    const mockData = [
      {
        id: "q1",
        session_id: "s1",
        question: "What color?",
        context: null,
        answered: false,
        answer: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchSessionQuestions("s1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/questions",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchSessionQuestions(sessionId, false) includes ?answered=false query param", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await fetchSessionQuestions("s1", false);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/questions?answered=false",
    );
  });

  it("fetchSessionQuestions throws on non-200 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(fetchSessionQuestions("s1")).rejects.toThrow(
      "Failed to fetch session questions: 404",
    );
  });

  it("answerQuestion calls POST with correct body and returns QuestionRead", async () => {
    const mockResponse = {
      id: "q1",
      session_id: "s1",
      question: "What color?",
      context: null,
      answered: true,
      answer: "Blue",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await answerQuestion("s1", "q1", "Blue");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/questions/q1/answer",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: "Blue" }),
      },
    );
    expect(result).toEqual(mockResponse);
  });

  it("answerQuestion throws on 409 (already answered)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 409 }),
    );

    await expect(answerQuestion("s1", "q1", "Blue")).rejects.toThrow(
      "Failed to answer question: 409",
    );
  });

  it("answerQuestion throws on 404 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(answerQuestion("s1", "q1", "Blue")).rejects.toThrow(
      "Failed to answer question: 404",
    );
  });
});
