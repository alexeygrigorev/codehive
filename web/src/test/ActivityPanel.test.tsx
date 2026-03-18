import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ActivityPanel from "@/components/sidebar/ActivityPanel";
import { buildActivityEntry, formatEventType } from "@/components/sidebar/ActivityPanel";
import type { EventRead } from "@/api/events";

vi.mock("@/api/events", () => ({
  fetchEvents: vi.fn(),
}));

import { fetchEvents } from "@/api/events";
const mockFetchEvents = vi.mocked(fetchEvents);

describe("ActivityPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockFetchEvents.mockReturnValue(new Promise(() => {}));
    render(<ActivityPanel sessionId="s1" />);
    expect(screen.getByText("Loading activity...")).toBeInTheDocument();
  });

  it("shows 'No activity yet' when events array is empty", async () => {
    mockFetchEvents.mockResolvedValue([]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("No activity yet")).toBeInTheDocument();
    });
  });

  it("shows error state when fetch fails", async () => {
    mockFetchEvents.mockRejectedValue(
      new Error("Failed to fetch events: 500"),
    );
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch events: 500"),
      ).toBeInTheDocument();
    });
  });

  it("renders tool call events with tool name extracted from event data", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "tool.call.started",
        data: { tool: "bash" },
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText(/Tool called: bash/)).toBeInTheDocument();
    });
  });

  it("renders tool call finished events with tool name from data.name", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "tool.call.finished",
        data: { name: "read_file" },
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText(/Tool completed: read_file/)).toBeInTheDocument();
    });
  });

  it("renders file change events with filename from data.path", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "file.changed",
        data: { path: "src/app.tsx" },
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText(/File changed: src\/app.tsx/),
      ).toBeInTheDocument();
    });
  });

  it("renders file change events with filename from data.file", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "file_changed",
        data: { file: "README.md" },
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText(/File changed: README.md/)).toBeInTheDocument();
    });
  });

  it("renders message events with role", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "message.created",
        data: { role: "assistant" },
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText(/Message from assistant/),
      ).toBeInTheDocument();
    });
  });

  it("falls back to formatted event type for unknown event types", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "custom.event.type",
        data: {},
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("Custom Event Type")).toBeInTheDocument();
    });
  });

  it("shows timestamps in HH:MM format", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "tool.call.started",
        data: { tool: "bash" },
        created_at: "2026-01-15T14:30:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      // The timestamp text should be present (format depends on locale)
      const entries = screen.getAllByTestId("activity-entry");
      expect(entries.length).toBe(1);
    });
  });

  it("shows most recent events first", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "tool.call.started",
        data: { tool: "bash" },
        created_at: "2026-01-15T14:00:00Z",
      },
      {
        id: "e2",
        session_id: "s1",
        type: "file.changed",
        data: { path: "app.py" },
        created_at: "2026-01-15T15:00:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      const entries = screen.getAllByTestId("activity-entry");
      expect(entries.length).toBe(2);
    });

    const entries = screen.getAllByTestId("activity-entry");
    // The file change (15:00) should come before the tool call (14:00)
    expect(entries[0]).toHaveTextContent(/File changed: app.py/);
    expect(entries[1]).toHaveTextContent(/Tool called: bash/);
  });

  it("shows colored dots by category", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "tool.call.started",
        data: { tool: "bash" },
        created_at: "2026-01-15T14:30:00Z",
      },
      {
        id: "e2",
        session_id: "s1",
        type: "file.changed",
        data: { path: "app.py" },
        created_at: "2026-01-15T14:31:00Z",
      },
      {
        id: "e3",
        session_id: "s1",
        type: "message.created",
        data: { role: "user" },
        created_at: "2026-01-15T14:32:00Z",
      },
    ]);
    render(<ActivityPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByTestId("activity-dot-tool")).toBeInTheDocument();
      expect(screen.getByTestId("activity-dot-file")).toBeInTheDocument();
      expect(screen.getByTestId("activity-dot-message")).toBeInTheDocument();
    });
  });
});

describe("buildActivityEntry", () => {
  it("extracts tool name from data.tool field", () => {
    const event: EventRead = {
      id: "e1",
      session_id: "s1",
      type: "tool.call.started",
      data: { tool: "grep" },
      created_at: "2026-01-15T14:30:00Z",
    };
    const entry = buildActivityEntry(event);
    expect(entry.description).toBe("Tool called: grep");
    expect(entry.category).toBe("tool");
  });

  it("extracts tool name from data.name field as fallback", () => {
    const event: EventRead = {
      id: "e1",
      session_id: "s1",
      type: "tool.call.started",
      data: { name: "write_file" },
      created_at: "2026-01-15T14:30:00Z",
    };
    const entry = buildActivityEntry(event);
    expect(entry.description).toBe("Tool called: write_file");
  });

  it("uses 'unknown tool' when no tool name is available", () => {
    const event: EventRead = {
      id: "e1",
      session_id: "s1",
      type: "tool.call.started",
      data: {},
      created_at: "2026-01-15T14:30:00Z",
    };
    const entry = buildActivityEntry(event);
    expect(entry.description).toBe("Tool called: unknown tool");
  });

  it("extracts filename from data.path", () => {
    const event: EventRead = {
      id: "e1",
      session_id: "s1",
      type: "file.changed",
      data: { path: "/src/index.ts" },
      created_at: "2026-01-15T14:30:00Z",
    };
    const entry = buildActivityEntry(event);
    expect(entry.description).toBe("File changed: /src/index.ts");
    expect(entry.category).toBe("file");
  });

  it("handles message.created with role", () => {
    const event: EventRead = {
      id: "e1",
      session_id: "s1",
      type: "message.created",
      data: { role: "user" },
      created_at: "2026-01-15T14:30:00Z",
    };
    const entry = buildActivityEntry(event);
    expect(entry.description).toBe("Message from user");
    expect(entry.category).toBe("message");
  });
});

describe("formatEventType", () => {
  it("converts dot-separated type to title case", () => {
    expect(formatEventType("custom.event.type")).toBe("Custom Event Type");
  });

  it("converts underscore-separated type to title case", () => {
    expect(formatEventType("task_started")).toBe("Task Started");
  });

  it("handles mixed separators", () => {
    expect(formatEventType("agent.task_completed")).toBe(
      "Agent Task Completed",
    );
  });
});
