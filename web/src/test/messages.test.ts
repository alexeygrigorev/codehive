import { describe, it, expect, vi, beforeEach } from "vitest";
import { sendMessage, fetchMessages } from "@/api/messages";

describe("messages API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("sendMessage", () => {
    it("calls POST to streaming endpoint and parses SSE events", async () => {
      const event = {
        id: "e1",
        session_id: "s1",
        type: "message.created",
        data: { role: "user", content: "hello" },
        created_at: "2026-01-01T00:00:00Z",
      };
      const sseBody = `data: ${JSON.stringify(event)}\n\n`;
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(sseBody, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      );

      const result = await sendMessage("s1", "hello");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost:7433/api/sessions/s1/messages/stream",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: "hello" }),
        },
      );
      expect(result).toEqual([event]);
    });

    it("calls onEvent callback for each SSE event", async () => {
      const event1 = {
        id: "e1",
        session_id: "s1",
        type: "message.delta",
        data: { content: "Hi" },
        created_at: "2026-01-01T00:00:00Z",
      };
      const event2 = {
        id: "e2",
        session_id: "s1",
        type: "message.delta",
        data: { content: " there" },
        created_at: "2026-01-01T00:00:01Z",
      };
      const sseBody = `data: ${JSON.stringify(event1)}\n\ndata: ${JSON.stringify(event2)}\n\n`;
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(sseBody, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      );

      const onEvent = vi.fn();
      const result = await sendMessage("s1", "hello", onEvent);

      expect(onEvent).toHaveBeenCalledTimes(2);
      expect(onEvent).toHaveBeenCalledWith(event1);
      expect(onEvent).toHaveBeenCalledWith(event2);
      expect(result).toEqual([event1, event2]);
    });

    it("throws on non-OK response", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response("", { status: 500 }),
      );

      await expect(sendMessage("s1", "hello")).rejects.toThrow(
        "Failed to send message: 500",
      );
    });
  });

  describe("fetchMessages", () => {
    it("calls GET with correct URL and returns parsed response", async () => {
      const events = [
        {
          id: "e1",
          session_id: "s1",
          type: "message.created",
          data: { role: "user", content: "hi" },
          created_at: "2026-01-01T00:00:00Z",
        },
      ];
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(JSON.stringify(events), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

      const result = await fetchMessages("s1");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost:7433/api/sessions/s1/messages",
      );
      expect(result).toEqual(events);
    });
  });
});
