import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchCheckpoints,
  createCheckpoint,
  rollbackCheckpoint,
} from "@/api/checkpoints";

describe("API: checkpoints", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchCheckpoints calls GET /api/sessions/{id}/checkpoints and returns parsed JSON", async () => {
    const mockData = [
      {
        id: "cp1",
        session_id: "s1",
        label: "before refactor",
        git_ref: "abc123",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchCheckpoints("s1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/checkpoints",
    );
    expect(result).toEqual(mockData);
  });

  it("createCheckpoint calls POST /api/sessions/{id}/checkpoints with label in body", async () => {
    const mockData = {
      id: "cp2",
      session_id: "s1",
      label: "my label",
      git_ref: "def456",
      created_at: "2026-01-01T00:01:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await createCheckpoint("s1", "my label");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/checkpoints",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: "my label" }),
      },
    );
    expect(result).toEqual(mockData);
  });

  it("rollbackCheckpoint calls POST /api/checkpoints/{id}/rollback", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 200 }),
    );

    await rollbackCheckpoint("cp1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/checkpoints/cp1/rollback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      },
    );
  });

  it("fetchCheckpoints throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchCheckpoints("s1")).rejects.toThrow(
      "Failed to fetch checkpoints: 500",
    );
  });
});
