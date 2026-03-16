import { describe, it, expect, vi, beforeEach } from "vitest";
import { startFlow, respondToFlow, finalizeFlow } from "@/api/projectFlow";

describe("API: projectFlow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("startFlow calls POST /api/project-flow/start with correct body", async () => {
    const mockResult = {
      flow_id: "f1",
      session_id: "s1",
      first_questions: [
        { id: "q1", text: "What is your goal?", category: "goals" },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResult), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await startFlow({
      flow_type: "brainstorm",
      initial_input: "My idea",
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/project-flow/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          flow_type: "brainstorm",
          initial_input: "My idea",
        }),
      }),
    );
    expect(result).toEqual(mockResult);
  });

  it("startFlow throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(
      startFlow({ flow_type: "brainstorm" }),
    ).rejects.toThrow("Failed to start flow: 500");
  });

  it("respondToFlow calls POST /api/project-flow/{flowId}/respond with answers", async () => {
    const mockResult = {
      next_questions: [
        { id: "q2", text: "Follow up?", category: "tech" },
      ],
      brief: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResult), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const answers = [{ question_id: "q1", answer: "My answer" }];
    const result = await respondToFlow("f1", answers);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/project-flow/f1/respond",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ answers }),
      }),
    );
    expect(result).toEqual(mockResult);
  });

  it("respondToFlow throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 400 }),
    );

    await expect(
      respondToFlow("f1", []),
    ).rejects.toThrow("Failed to respond to flow: 400");
  });

  it("finalizeFlow calls POST /api/project-flow/{flowId}/finalize", async () => {
    const mockResult = {
      project_id: "proj-1",
      sessions: [{ id: "s1", name: "Setup", mode: "execution" }],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResult), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await finalizeFlow("f1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/project-flow/f1/finalize",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({}),
      }),
    );
    expect(result).toEqual(mockResult);
  });

  it("finalizeFlow throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 422 }),
    );

    await expect(finalizeFlow("f1")).rejects.toThrow(
      "Failed to finalize flow: 422",
    );
  });
});
