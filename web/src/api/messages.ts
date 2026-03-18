import { apiClient } from "./client";
import type { SessionEvent } from "./websocket";

/**
 * Send a message via the SSE streaming endpoint.
 * Parses SSE events as they arrive and calls onEvent for each one.
 * Returns when the stream is complete.
 */
export async function sendMessage(
  sessionId: string,
  content: string,
  onEvent?: (event: SessionEvent) => void,
): Promise<SessionEvent[]> {
  const url = `${apiClient.baseURL}/api/sessions/${sessionId}/messages/stream`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.status}`);
  }

  const allEvents: SessionEvent[] = [];

  if (!response.body) {
    // Fallback: no streaming body available, try JSON parse
    const data = await response.json();
    const events = data as SessionEvent[];
    for (const event of events) {
      allEvents.push(event);
      onEvent?.(event);
    }
    return allEvents;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE lines
    const lines = buffer.split("\n");
    // Keep the last (possibly incomplete) line in the buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith(":")) {
        // Empty line or SSE comment, skip
        continue;
      }
      if (trimmed.startsWith("data: ")) {
        const jsonStr = trimmed.slice(6);
        if (jsonStr === "[DONE]") {
          continue;
        }
        try {
          const event = JSON.parse(jsonStr) as SessionEvent;
          allEvents.push(event);
          onEvent?.(event);
        } catch {
          // Skip malformed JSON lines
          console.warn("SSE: failed to parse event:", jsonStr);
        }
      }
    }
  }

  // Process any remaining buffer
  if (buffer.trim()) {
    const trimmed = buffer.trim();
    if (trimmed.startsWith("data: ")) {
      const jsonStr = trimmed.slice(6);
      if (jsonStr !== "[DONE]") {
        try {
          const event = JSON.parse(jsonStr) as SessionEvent;
          allEvents.push(event);
          onEvent?.(event);
        } catch {
          console.warn("SSE: failed to parse final event:", jsonStr);
        }
      }
    }
  }

  return allEvents;
}

export async function fetchMessages(
  sessionId: string,
): Promise<SessionEvent[]> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/messages`,
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch messages: ${response.status}`);
  }
  return response.json() as Promise<SessionEvent[]>;
}
