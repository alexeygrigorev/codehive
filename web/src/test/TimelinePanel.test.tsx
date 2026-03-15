import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import TimelinePanel from "@/components/sidebar/TimelinePanel";

vi.mock("@/api/events", () => ({
  fetchEvents: vi.fn(),
}));

import { fetchEvents } from "@/api/events";
const mockFetchEvents = vi.mocked(fetchEvents);

describe("TimelinePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockFetchEvents.mockReturnValue(new Promise(() => {}));
    render(<TimelinePanel sessionId="s1" />);
    expect(screen.getByText("Loading timeline...")).toBeInTheDocument();
  });

  it("renders events with type and formatted timestamp", async () => {
    mockFetchEvents.mockResolvedValue([
      {
        id: "e1",
        session_id: "s1",
        type: "task_started",
        data: {},
        created_at: "2026-01-15T14:30:00Z",
      },
      {
        id: "e2",
        session_id: "s1",
        type: "file_changed",
        data: {},
        created_at: "2026-01-15T14:35:00Z",
      },
    ]);
    render(<TimelinePanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("task_started")).toBeInTheDocument();
    });
    expect(screen.getByText("file_changed")).toBeInTheDocument();
  });

  it("shows empty state when no events exist", async () => {
    mockFetchEvents.mockResolvedValue([]);
    render(<TimelinePanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("No events yet")).toBeInTheDocument();
    });
  });

  it("shows error state when fetch fails", async () => {
    mockFetchEvents.mockRejectedValue(
      new Error("Failed to fetch events: 500"),
    );
    render(<TimelinePanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch events: 500"),
      ).toBeInTheDocument();
    });
  });
});
