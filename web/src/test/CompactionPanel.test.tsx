import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/api/events", () => ({
  fetchEventsByType: vi.fn(),
}));

vi.mock("@/api/sessions", () => ({
  updateSession: vi.fn(),
}));

import { fetchEventsByType } from "@/api/events";
import { updateSession } from "@/api/sessions";
import CompactionPanel from "@/components/sidebar/CompactionPanel";

const mockFetchEventsByType = vi.mocked(fetchEventsByType);
const mockUpdateSession = vi.mocked(updateSession);

function makeSession(config: Record<string, unknown> = {}) {
  return {
    id: "s1",
    project_id: "p1",
    issue_id: null,
    parent_session_id: null,
    name: "Test Session",
    engine: "native",
    mode: "execution",
    status: "idle",
    config,
    created_at: new Date().toISOString(),
  };
}

describe("CompactionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchEventsByType.mockResolvedValue([]);
    mockUpdateSession.mockResolvedValue(makeSession());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders with correct defaults when no config keys are set", async () => {
    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    // Panel renders synchronously; history loads async
    expect(screen.getByTestId("compaction-panel")).toBeInTheDocument();

    // Toggle should be ON by default
    const toggle = screen.getByTestId("compaction-toggle");
    expect(toggle).toHaveAttribute("aria-checked", "true");

    // Threshold should show 80%
    expect(screen.getByTestId("threshold-value")).toHaveTextContent("80%");

    // Keep recent should show 4
    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("4");
  });

  it("renders with values from session config", () => {
    const session = makeSession({
      compaction_enabled: false,
      compaction_threshold: 0.7,
      compaction_preserve_last_n: 6,
    });

    render(<CompactionPanel sessionId="s1" session={session} />);

    expect(screen.getByTestId("compaction-toggle")).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByTestId("threshold-value")).toHaveTextContent("70%");
    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("6");
  });

  it("toggling auto-compaction calls updateSession", async () => {
    const user = userEvent.setup();
    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    await user.click(screen.getByTestId("compaction-toggle"));

    expect(mockUpdateSession).toHaveBeenCalledWith("s1", {
      config: expect.objectContaining({ compaction_enabled: false }),
    });
  });

  it("clicking + on keep-recent increases value and saves after debounce", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("4");

    await user.click(screen.getByTestId("keep-recent-plus"));

    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("5");

    // Wait for debounce
    await act(async () => {
      vi.advanceTimersByTime(600);
    });

    expect(mockUpdateSession).toHaveBeenCalledWith("s1", {
      config: expect.objectContaining({ compaction_preserve_last_n: 5 }),
    });
  });

  it("clicking - on keep-recent decreases value", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const session = makeSession({ compaction_preserve_last_n: 6 });
    render(<CompactionPanel sessionId="s1" session={session} />);

    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("6");

    await user.click(screen.getByTestId("keep-recent-minus"));

    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("5");

    await act(async () => {
      vi.advanceTimersByTime(600);
    });

    expect(mockUpdateSession).toHaveBeenCalledWith("s1", {
      config: expect.objectContaining({ compaction_preserve_last_n: 5 }),
    });
  });

  it("keep-recent cannot go below 2", () => {
    const session = makeSession({ compaction_preserve_last_n: 2 });
    render(<CompactionPanel sessionId="s1" session={session} />);

    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("2");
    expect(screen.getByTestId("keep-recent-minus")).toBeDisabled();
  });

  it("keep-recent cannot go above 10", () => {
    const session = makeSession({ compaction_preserve_last_n: 10 });
    render(<CompactionPanel sessionId="s1" session={session} />);

    expect(screen.getByTestId("keep-recent-value")).toHaveTextContent("10");
    expect(screen.getByTestId("keep-recent-plus")).toBeDisabled();
  });

  it("shows no-history message when no compaction events", async () => {
    mockFetchEventsByType.mockResolvedValue([]);
    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    await waitFor(() => {
      expect(screen.getByTestId("no-history")).toBeInTheDocument();
    });
  });

  it("displays compaction history entries", async () => {
    mockFetchEventsByType.mockResolvedValue([
      {
        id: "ev1",
        session_id: "s1",
        type: "context.compacted",
        data: {
          messages_compacted: 12,
          messages_preserved: 4,
          summary_text: "Summary of conversation about authentication flow",
          threshold_percent: 82.3,
        },
        created_at: new Date().toISOString(),
      },
    ]);

    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    await waitFor(() => {
      expect(screen.getByTestId("compaction-history-entry")).toBeInTheDocument();
    });

    expect(screen.getByText("12 compacted")).toBeInTheDocument();
  });

  it("expands and collapses history entries on click", async () => {
    const user = userEvent.setup();
    mockFetchEventsByType.mockResolvedValue([
      {
        id: "ev1",
        session_id: "s1",
        type: "context.compacted",
        data: {
          messages_compacted: 12,
          messages_preserved: 4,
          summary_text: "Full summary text here",
          threshold_percent: 82.3,
        },
        created_at: new Date().toISOString(),
      },
    ]);

    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    await waitFor(() => {
      expect(screen.getByTestId("compaction-history-entry")).toBeInTheDocument();
    });

    // Click to expand
    await user.click(screen.getByTestId("compaction-history-entry"));

    expect(
      screen.getByTestId("compaction-history-expanded"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Messages compacted: 12/)).toBeInTheDocument();
    expect(screen.getByText(/Messages preserved: 4/)).toBeInTheDocument();

    // Click again to collapse
    await user.click(screen.getByTestId("compaction-history-entry"));

    expect(
      screen.queryByTestId("compaction-history-expanded"),
    ).not.toBeInTheDocument();
  });

  it("fetches compaction history with correct event type", async () => {
    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    await waitFor(() => {
      expect(mockFetchEventsByType).toHaveBeenCalledWith(
        "s1",
        "context.compacted",
      );
    });
  });

  it("threshold slider changes update displayed value", () => {
    render(<CompactionPanel sessionId="s1" session={makeSession()} />);

    const slider = screen.getByTestId("compaction-threshold");
    fireEvent.change(slider, { target: { value: "0.70" } });

    expect(screen.getByTestId("threshold-value")).toHaveTextContent("70%");
  });
});
