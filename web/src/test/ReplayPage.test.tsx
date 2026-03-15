import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/replay", () => ({
  fetchReplay: vi.fn(),
}));

import { fetchReplay } from "@/api/replay";
import ReplayPage from "@/pages/ReplayPage";

const mockFetchReplay = vi.mocked(fetchReplay);

function renderReplayPage(sessionId = "sess-123") {
  return render(
    <MemoryRouter initialEntries={[`/sessions/${sessionId}/replay`]}>
      <Routes>
        <Route
          path="/sessions/:sessionId/replay"
          element={<ReplayPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

const mockReplayData = {
  session_id: "sess-123",
  session_status: "completed",
  total_steps: 3,
  steps: [
    {
      index: 0,
      timestamp: "2026-01-01T12:00:00Z",
      step_type: "message",
      data: { role: "user", content: "hello" },
    },
    {
      index: 1,
      timestamp: "2026-01-01T12:00:01Z",
      step_type: "tool_call_start",
      data: { tool: "edit_file" },
    },
    {
      index: 2,
      timestamp: "2026-01-01T12:00:02Z",
      step_type: "tool_call_finish",
      data: { tool: "edit_file", output: "done" },
    },
  ],
};

describe("ReplayPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state while fetching", () => {
    mockFetchReplay.mockReturnValue(new Promise(() => {}));
    renderReplayPage();
    expect(screen.getByText("Loading replay...")).toBeInTheDocument();
  });

  it("fetches and renders the first step on load", async () => {
    mockFetchReplay.mockResolvedValue(mockReplayData);
    renderReplayPage();

    await waitFor(() => {
      expect(screen.getByText("hello")).toBeInTheDocument();
    });
    expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
  });

  it("clicking Next advances to the next step", async () => {
    mockFetchReplay.mockResolvedValue(mockReplayData);
    renderReplayPage();

    await waitFor(() => {
      expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();
  });

  it("clicking Previous goes back", async () => {
    mockFetchReplay.mockResolvedValue(mockReplayData);
    renderReplayPage();

    await waitFor(() => {
      expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
  });

  it("Previous is disabled on first step; Next disabled on last", async () => {
    mockFetchReplay.mockResolvedValue(mockReplayData);
    renderReplayPage();

    await waitFor(() => {
      expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled();

    // Navigate to last step
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText("Step 3 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Previous" }),
    ).not.toBeDisabled();
  });

  it("shows error message if fetch fails", async () => {
    mockFetchReplay.mockRejectedValue(
      new Error("Failed to fetch replay: 409"),
    );
    renderReplayPage();

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch replay: 409"),
      ).toBeInTheDocument();
    });
  });
});
