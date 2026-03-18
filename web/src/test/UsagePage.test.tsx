import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/usage", () => ({
  fetchUsage: vi.fn(),
  fetchUsageSummary: vi.fn(),
  fetchSessionUsage: vi.fn(),
}));

import { fetchUsage } from "@/api/usage";
import UsagePage from "@/pages/UsagePage";

const mockFetchUsage = vi.mocked(fetchUsage);

const mockUsageResponse = {
  records: [
    {
      id: "r1",
      session_id: "s1",
      model: "claude-sonnet-4-20250514",
      input_tokens: 1500,
      output_tokens: 800,
      estimated_cost: 0.0165,
      created_at: "2026-03-18T10:00:00",
    },
  ],
  summary: {
    total_requests: 1,
    total_input_tokens: 1500,
    total_output_tokens: 800,
    estimated_cost: 0.0165,
  },
};

function renderUsagePage() {
  return render(
    <MemoryRouter initialEntries={["/usage"]}>
      <UsagePage />
    </MemoryRouter>,
  );
}

describe("UsagePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchUsage.mockResolvedValue(mockUsageResponse);
  });

  it("renders page title", async () => {
    renderUsagePage();
    expect(screen.getByText("Usage")).toBeInTheDocument();
  });

  it("renders summary cards after loading", async () => {
    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByTestId("total-requests")).toHaveTextContent("1");
    });
    expect(screen.getByTestId("estimated-cost")).toHaveTextContent("$0.02");
  });

  it("renders usage table with records", async () => {
    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByTestId("usage-table")).toBeInTheDocument();
    });

    expect(screen.getByText("claude-sonnet-4-20250514")).toBeInTheDocument();
  });

  it("renders time range selector", () => {
    renderUsagePage();
    expect(screen.getByTestId("time-range-select")).toBeInTheDocument();
  });

  it("fetches data on time range change", async () => {
    renderUsagePage();

    await waitFor(() => {
      expect(mockFetchUsage).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId("time-range-select"), {
      target: { value: "today" },
    });

    await waitFor(() => {
      // Should have been called again with new range
      expect(mockFetchUsage).toHaveBeenCalledTimes(2);
    });
  });

  it("shows empty state when no records", async () => {
    mockFetchUsage.mockResolvedValue({
      records: [],
      summary: {
        total_requests: 0,
        total_input_tokens: 0,
        total_output_tokens: 0,
        estimated_cost: 0,
      },
    });

    renderUsagePage();

    await waitFor(() => {
      expect(
        screen.getByText("No usage records found for the selected time range."),
      ).toBeInTheDocument();
    });
  });
});
