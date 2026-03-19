import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/usage", () => ({
  fetchUsage: vi.fn(),
  fetchUsageLimits: vi.fn(),
  fetchUsageSummary: vi.fn(),
  fetchSessionUsage: vi.fn(),
}));

import { fetchUsage, fetchUsageLimits } from "@/api/usage";
import UsagePage from "@/pages/UsagePage";

const mockFetchUsage = vi.mocked(fetchUsage);
const mockFetchUsageLimits = vi.mocked(fetchUsageLimits);

const emptyLimitsResponse = {
  rate_limits: [],
  model_usage: [],
};

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
    mockFetchUsageLimits.mockResolvedValue(emptyLimitsResponse);
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

describe("UsagePage - Plan Limits", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchUsage.mockResolvedValue({
      records: [],
      summary: {
        total_requests: 0,
        total_input_tokens: 0,
        total_output_tokens: 0,
        estimated_cost: 0,
      },
    });
  });

  it("shows placeholder when no rate limit data exists", async () => {
    mockFetchUsageLimits.mockResolvedValue(emptyLimitsResponse);
    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByTestId("plan-limits-empty")).toBeInTheDocument();
    });
    expect(
      screen.getByText("No plan usage data yet. Run a Claude Code session to see limits."),
    ).toBeInTheDocument();
  });

  it("renders plan limits section with heading", async () => {
    mockFetchUsageLimits.mockResolvedValue(emptyLimitsResponse);
    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByTestId("plan-limits-section")).toBeInTheDocument();
    });
    expect(screen.getByText("Plan Limits")).toBeInTheDocument();
    expect(screen.getByText("Claude Code Plan")).toBeInTheDocument();
  });

  it("renders progress bars with correct percentages", async () => {
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [
        {
          rate_limit_type: "seven_day",
          utilization: 0.85,
          resets_at: Math.floor(Date.now() / 1000) + 86400,
          is_using_overage: false,
          surpassed_threshold: 0.75,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
      model_usage: [],
    });

    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByTestId("rate-limit-seven_day")).toBeInTheDocument();
    });
    expect(screen.getByText("85% used")).toBeInTheDocument();
    expect(screen.getByText("Weekly")).toBeInTheDocument();
  });

  it("shows amber color for utilization between 80-95%", async () => {
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [
        {
          rate_limit_type: "seven_day",
          utilization: 0.85,
          resets_at: Math.floor(Date.now() / 1000) + 3600,
          is_using_overage: false,
          surpassed_threshold: null,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
      model_usage: [],
    });

    renderUsagePage();

    await waitFor(() => {
      const bar = screen.getByTestId("rate-limit-bar-seven_day");
      expect(bar.className).toContain("bg-amber-500");
    });
  });

  it("shows red color for utilization above 95%", async () => {
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [
        {
          rate_limit_type: "seven_day",
          utilization: 0.97,
          resets_at: Math.floor(Date.now() / 1000) + 3600,
          is_using_overage: false,
          surpassed_threshold: null,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
      model_usage: [],
    });

    renderUsagePage();

    await waitFor(() => {
      const bar = screen.getByTestId("rate-limit-bar-seven_day");
      expect(bar.className).toContain("bg-red-500");
    });
  });

  it("shows green color for utilization below 80%", async () => {
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [
        {
          rate_limit_type: "seven_day",
          utilization: 0.5,
          resets_at: Math.floor(Date.now() / 1000) + 3600,
          is_using_overage: false,
          surpassed_threshold: null,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
      model_usage: [],
    });

    renderUsagePage();

    await waitFor(() => {
      const bar = screen.getByTestId("rate-limit-bar-seven_day");
      expect(bar.className).toContain("bg-green-500");
    });
  });

  it("shows Overage label when isUsingOverage is true", async () => {
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [
        {
          rate_limit_type: "seven_day",
          utilization: 0.99,
          resets_at: Math.floor(Date.now() / 1000) + 3600,
          is_using_overage: true,
          surpassed_threshold: 0.95,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
      model_usage: [],
    });

    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByText("Overage")).toBeInTheDocument();
    });
  });

  it("renders per-model breakdown table", async () => {
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [],
      model_usage: [
        {
          model: "claude-opus-4-20250514",
          input_tokens: 5000,
          output_tokens: 1200,
          cache_read_tokens: 3000,
          cache_creation_tokens: 500,
          cost_usd: 0.07,
          context_window: 200000,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
    });

    renderUsagePage();

    await waitFor(() => {
      expect(screen.getByTestId("model-usage-table")).toBeInTheDocument();
    });
    expect(screen.getByText("claude-opus-4-20250514")).toBeInTheDocument();
    expect(screen.getByText("$0.07")).toBeInTheDocument();
    expect(screen.getByText("Per-Model Costs")).toBeInTheDocument();
  });

  it("displays reset time text", async () => {
    const futureReset = Math.floor(Date.now() / 1000) + 7200; // 2 hours from now
    mockFetchUsageLimits.mockResolvedValue({
      rate_limits: [
        {
          rate_limit_type: "seven_day",
          utilization: 0.5,
          resets_at: futureReset,
          is_using_overage: false,
          surpassed_threshold: null,
          captured_at: "2026-03-19T10:00:00",
        },
      ],
      model_usage: [],
    });

    renderUsagePage();

    await waitFor(() => {
      const el = screen.getByTestId("rate-limit-seven_day");
      expect(el.textContent).toMatch(/resets in/);
    });
  });
});
