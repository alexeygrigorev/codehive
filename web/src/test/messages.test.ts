import { describe, it, expect, vi, beforeEach } from "vitest";
import { sendMessage, fetchMessages } from "@/api/messages";

describe("messages API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("sendMessage", () => {
    it("calls POST with correct URL and body, returns parsed response", async () => {
      const events = [
        {
          id: "e1",
          session_id: "s1",
          type: "message.created",
          data: { role: "user", content: "hello" },
          created_at: "2026-01-01T00:00:00Z",
        },
      ];
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(JSON.stringify(events), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

      const result = await sendMessage("s1", "hello");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/sessions/s1/messages",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: "hello" }),
        },
      );
      expect(result).toEqual(events);
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
        "http://localhost:8000/api/sessions/s1/messages",
      );
      expect(result).toEqual(events);
    });
  });
});
