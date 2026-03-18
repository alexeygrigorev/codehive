import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/usage", () => ({
  fetchSessionUsage: vi.fn(),
}));

import { fetchSessionUsage } from "@/api/usage";
import UsagePanel from "@/components/sidebar/UsagePanel";

const mockFetchSessionUsage = vi.mocked(fetchSessionUsage);

describe("UsagePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders usage data after loading", async () => {
    mockFetchSessionUsage.mockResolvedValue({
      total_requests: 5,
      total_input_tokens: 10000,
      total_output_tokens: 5000,
      estimated_cost: 0.1234,
    });

    render(<UsagePanel sessionId="test-session-id" />);

    await waitFor(() => {
      expect(screen.getByTestId("usage-panel")).toBeInTheDocument();
    });

    expect(screen.getByTestId("session-input-tokens")).toHaveTextContent(
      "10.0K",
    );
    expect(screen.getByTestId("session-output-tokens")).toHaveTextContent(
      "5.0K",
    );
    expect(screen.getByTestId("session-requests")).toHaveTextContent("5");
    expect(screen.getByTestId("session-cost")).toHaveTextContent("$0.1234");
  });

  it("shows loading state initially", () => {
    mockFetchSessionUsage.mockReturnValue(new Promise(() => {})); // never resolves
    render(<UsagePanel sessionId="test-session-id" />);
    expect(screen.getByText("Loading usage...")).toBeInTheDocument();
  });

  it("shows error on fetch failure", async () => {
    mockFetchSessionUsage.mockRejectedValue(new Error("Network error"));

    render(<UsagePanel sessionId="test-session-id" />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("calls fetchSessionUsage with session ID", async () => {
    mockFetchSessionUsage.mockResolvedValue({
      total_requests: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      estimated_cost: 0,
    });

    render(<UsagePanel sessionId="my-session-id" />);

    await waitFor(() => {
      expect(mockFetchSessionUsage).toHaveBeenCalledWith("my-session-id");
    });
  });
});
