import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { normalizeEvent } from "@/api/websocket.ts";

// Mock crypto.randomUUID for deterministic tests
const MOCK_UUID = "00000000-0000-0000-0000-000000000000";

describe("normalizeEvent", () => {
  beforeEach(() => {
    vi.stubGlobal("crypto", {
      ...globalThis.crypto,
      randomUUID: () => MOCK_UUID,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("passes through a properly-shaped SessionEvent unchanged", () => {
    const raw: Record<string, unknown> = {
      id: "evt-1",
      session_id: "sess-1",
      type: "message.created",
      data: { role: "assistant", content: "Hello" },
      created_at: "2026-01-01T00:00:00Z",
    };

    const result = normalizeEvent(raw);

    expect(result.id).toBe("evt-1");
    expect(result.session_id).toBe("sess-1");
    expect(result.type).toBe("message.created");
    expect(result.data.role).toBe("assistant");
    expect(result.data.content).toBe("Hello");
    expect(result.created_at).toBe("2026-01-01T00:00:00Z");
  });

  it("normalizes a flat event (no data wrapper) into SessionEvent shape", () => {
    const raw: Record<string, unknown> = {
      type: "message.created",
      role: "user",
      content: "Hi there",
    };

    const result = normalizeEvent(raw);

    expect(result.type).toBe("message.created");
    expect(result.data.role).toBe("user");
    expect(result.data.content).toBe("Hi there");
    // Should have generated an id
    expect(result.id).toBe(MOCK_UUID);
    expect(result.session_id).toBe("");
  });

  it("preserves id and session_id from flat events when present", () => {
    const raw: Record<string, unknown> = {
      id: "flat-1",
      session_id: "s1",
      type: "message.created",
      role: "assistant",
      content: "Response",
      created_at: "2026-03-17T00:00:00Z",
    };

    const result = normalizeEvent(raw);

    expect(result.id).toBe("flat-1");
    expect(result.session_id).toBe("s1");
    expect(result.data.role).toBe("assistant");
    expect(result.data.content).toBe("Response");
    expect(result.created_at).toBe("2026-03-17T00:00:00Z");
  });

  it("treats data: null as a flat event", () => {
    const raw: Record<string, unknown> = {
      id: "e1",
      type: "message.created",
      data: null,
      role: "user",
      content: "test",
    };

    const result = normalizeEvent(raw);

    // data was null, so role/content should be in data now
    expect(result.data.role).toBe("user");
    expect(result.data.content).toBe("test");
  });

  it("treats data as array as a flat event", () => {
    const raw: Record<string, unknown> = {
      id: "e1",
      type: "message.created",
      data: ["some", "array"],
      role: "user",
      content: "test",
    };

    const result = normalizeEvent(raw);

    expect(result.data.role).toBe("user");
    expect(result.data.content).toBe("test");
  });

  it("event.data.role and event.data.content are accessible strings for message events", () => {
    // Standard event from WebSocket
    const wsEvent: Record<string, unknown> = {
      id: "ws-1",
      session_id: "s1",
      type: "message.created",
      data: { role: "assistant", content: "Hello from WS" },
      created_at: "2026-01-01T00:00:00Z",
    };

    const result = normalizeEvent(wsEvent);
    expect(typeof result.data.role).toBe("string");
    expect(typeof result.data.content).toBe("string");
    expect(result.data.role).toBe("assistant");
    expect(result.data.content).toBe("Hello from WS");
  });
});
