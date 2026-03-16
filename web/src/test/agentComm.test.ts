import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchAgentMessages } from "@/api/agentComm";

describe("API: agentComm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("filters events to only agent.message and agent.query types", async () => {
    const mockData = [
      {
        id: "e1",
        session_id: "session-1",
        type: "agent.message",
        data: {
          sender_session_id: "s1",
          target_session_id: "s2",
          message: "hello",
          timestamp: "2026-01-01T00:00:00Z",
        },
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "e2",
        session_id: "session-1",
        type: "agent.message",
        data: {
          sender_session_id: "s2",
          target_session_id: "s1",
          message: "hi back",
          timestamp: "2026-01-01T00:01:00Z",
        },
        created_at: "2026-01-01T00:01:00Z",
      },
      {
        id: "e3",
        session_id: "session-1",
        type: "agent.message",
        data: {
          sender_session_id: "s1",
          target_session_id: "s3",
          message: "ping",
          timestamp: "2026-01-01T00:02:00Z",
        },
        created_at: "2026-01-01T00:02:00Z",
      },
      {
        id: "e4",
        session_id: "session-1",
        type: "agent.query",
        data: {
          sender_session_id: "s1",
          target_session_id: "s2",
          message: "what status?",
          timestamp: "2026-01-01T00:03:00Z",
        },
        created_at: "2026-01-01T00:03:00Z",
      },
      {
        id: "e5",
        session_id: "session-1",
        type: "file.changed",
        data: { path: "/foo.txt" },
        created_at: "2026-01-01T00:04:00Z",
      },
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchAgentMessages("session-1");

    expect(result).toHaveLength(4);
    expect(result.every((e) => ["agent.message", "agent.query"].includes(e.type))).toBe(true);
    expect(result.find((e) => e.id === "e5")).toBeUndefined();
  });

  it("returns empty array when no events exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchAgentMessages("session-1");

    expect(result).toEqual([]);
  });

  it("throws an error on non-200 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchAgentMessages("session-1")).rejects.toThrow(
      "Failed to fetch agent messages: 500",
    );
  });
});
