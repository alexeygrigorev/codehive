import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChangedFilesPanel from "@/components/sidebar/ChangedFilesPanel";

vi.mock("@/api/diffs", () => ({
  fetchSessionDiffs: vi.fn(),
}));

import { fetchSessionDiffs } from "@/api/diffs";
const mockFetchDiffs = vi.mocked(fetchSessionDiffs);

describe("ChangedFilesPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockFetchDiffs.mockReturnValue(new Promise(() => {}));
    render(<ChangedFilesPanel sessionId="s1" />);
    expect(screen.getByText("Loading changed files...")).toBeInTheDocument();
  });

  it("renders file paths with addition and deletion counts", async () => {
    mockFetchDiffs.mockResolvedValue({
      session_id: "s1",
      files: [
        { path: "src/auth.py", diff_text: "...", additions: 12, deletions: 3 },
        { path: "src/main.py", diff_text: "...", additions: 5, deletions: 0 },
      ],
    });
    render(<ChangedFilesPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("src/auth.py")).toBeInTheDocument();
    });
    expect(screen.getByText("src/main.py")).toBeInTheDocument();
    expect(screen.getByText("+12")).toBeInTheDocument();
    expect(screen.getByText("-3")).toBeInTheDocument();
    expect(screen.getByText("+5")).toBeInTheDocument();
    expect(screen.getByText("-0")).toBeInTheDocument();
  });

  it("shows empty state when no files are changed", async () => {
    mockFetchDiffs.mockResolvedValue({ session_id: "s1", files: [] });
    render(<ChangedFilesPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("No changed files")).toBeInTheDocument();
    });
  });

  it("shows error state when fetch fails", async () => {
    mockFetchDiffs.mockRejectedValue(
      new Error("Failed to fetch session diffs: 500"),
    );
    render(<ChangedFilesPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch session diffs: 500"),
      ).toBeInTheDocument();
    });
  });
});
