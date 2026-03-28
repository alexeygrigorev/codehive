import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

import { apiClient } from "@/api/client";
import SpawnConfigPanel from "@/components/sidebar/SpawnConfigPanel";

const mockGet = vi.mocked(apiClient.get);

function makeSessionResponse(spawnConfig: Record<string, unknown> | null) {
  return {
    ok: true,
    json: async () => ({
      id: "s1",
      config: spawnConfig ? { spawn_config: spawnConfig } : {},
    }),
  } as unknown as Response;
}

describe("SpawnConfigPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders spawn config sections when data exists", async () => {
    mockGet.mockResolvedValue(
      makeSessionResponse({
        system_prompt: "You are a SWE agent.",
        initial_message: "Implement feature X.",
        engine: "claude_code",
        engine_args: ["--verbose"],
        role: "swe",
        pipeline_step: "implementing",
      }),
    );

    render(<SpawnConfigPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByTestId("spawn-config-panel")).toBeInTheDocument();
    });

    expect(screen.getByTestId("spawn-system-prompt")).toHaveTextContent(
      "You are a SWE agent.",
    );
    expect(screen.getByTestId("spawn-initial-message")).toHaveTextContent(
      "Implement feature X.",
    );
    expect(screen.getByTestId("spawn-engine-args")).toHaveTextContent("claude_code");
    expect(screen.getByTestId("spawn-engine-args")).toHaveTextContent("--verbose");
  });

  it("shows empty state for sessions without spawn config", async () => {
    mockGet.mockResolvedValue(makeSessionResponse(null));

    render(<SpawnConfigPanel sessionId="s2" />);

    await waitFor(() => {
      expect(screen.getByTestId("spawn-config-empty")).toBeInTheDocument();
    });

    expect(
      screen.getByText("No spawn configuration recorded for this session"),
    ).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<SpawnConfigPanel sessionId="s3" />);
    expect(screen.getByText("Loading spawn config...")).toBeInTheDocument();
  });

  it("shows error on fetch failure", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));

    render(<SpawnConfigPanel sessionId="s4" />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("calls API with correct session ID", async () => {
    mockGet.mockResolvedValue(makeSessionResponse(null));

    render(<SpawnConfigPanel sessionId="my-session-id" />);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/sessions/my-session-id");
    });
  });
});
