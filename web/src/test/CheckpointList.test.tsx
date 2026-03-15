import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import CheckpointList from "@/components/CheckpointList";

vi.mock("@/api/checkpoints", () => ({
  fetchCheckpoints: vi.fn(),
  rollbackCheckpoint: vi.fn(),
  createCheckpoint: vi.fn(),
}));

import { fetchCheckpoints, rollbackCheckpoint } from "@/api/checkpoints";
const mockFetchCheckpoints = vi.mocked(fetchCheckpoints);
const mockRollbackCheckpoint = vi.mocked(rollbackCheckpoint);

const mockCheckpoints = [
  {
    id: "cp1",
    session_id: "s1",
    label: "before refactor",
    git_ref: "abc123",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "cp2",
    session_id: "s1",
    label: null,
    git_ref: "def456",
    created_at: "2026-01-01T01:00:00Z",
  },
];

describe("CheckpointList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetch is pending", () => {
    mockFetchCheckpoints.mockReturnValue(new Promise(() => {}));
    render(<CheckpointList sessionId="s1" />);
    expect(screen.getByText("Loading checkpoints...")).toBeInTheDocument();
  });

  it("shows empty state when no checkpoints returned", async () => {
    mockFetchCheckpoints.mockResolvedValue([]);
    render(<CheckpointList sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("No checkpoints")).toBeInTheDocument();
    });
  });

  it("renders checkpoint items with label, git ref, and timestamp", async () => {
    mockFetchCheckpoints.mockResolvedValue(mockCheckpoints);
    render(<CheckpointList sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("before refactor")).toBeInTheDocument();
    });
    expect(screen.getByText("abc123")).toBeInTheDocument();
    expect(screen.getByText("2026-01-01T00:00:00Z")).toBeInTheDocument();
    // Second checkpoint has no label, should show id
    expect(screen.getByText("cp2")).toBeInTheDocument();
  });

  it("renders a Restore button per checkpoint", async () => {
    mockFetchCheckpoints.mockResolvedValue(mockCheckpoints);
    render(<CheckpointList sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("before refactor")).toBeInTheDocument();
    });

    const restoreButtons = screen.getAllByText("Restore");
    expect(restoreButtons).toHaveLength(2);
  });

  it("calls rollbackCheckpoint when Restore button is clicked", async () => {
    const user = userEvent.setup();
    mockFetchCheckpoints.mockResolvedValue(mockCheckpoints);
    mockRollbackCheckpoint.mockResolvedValue(undefined);
    render(<CheckpointList sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("before refactor")).toBeInTheDocument();
    });

    const restoreButtons = screen.getAllByText("Restore");
    await user.click(restoreButtons[0]);

    expect(mockRollbackCheckpoint).toHaveBeenCalledWith("cp1");
  });

  it("shows error state when fetch fails", async () => {
    mockFetchCheckpoints.mockRejectedValue(
      new Error("Failed to fetch checkpoints: 500"),
    );
    render(<CheckpointList sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch checkpoints: 500"),
      ).toBeInTheDocument();
    });
  });
});
