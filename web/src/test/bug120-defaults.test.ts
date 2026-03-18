/**
 * Bug #120 regression tests: default engine should be "claude_code", not "native".
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createSession } from "@/api/sessions";

describe("Bug 120: createSession default engine", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("createSession uses claude_code as the default engine (not native)", async () => {
    const mockData = {
      id: "s1",
      project_id: "p1",
      issue_id: null,
      parent_session_id: null,
      name: "Test Session",
      engine: "claude_code",
      mode: "execution",
      status: "idle",
      config: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await createSession("p1", { name: "Test Session" });

    const fetchCall = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse((fetchCall[1] as RequestInit).body as string);
    expect(body.engine).toBe("claude_code");
  });
});
