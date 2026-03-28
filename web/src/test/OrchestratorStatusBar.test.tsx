import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import OrchestratorStatusBar from "@/components/pipeline/OrchestratorStatusBar";
import type { OrchestratorStatus } from "@/api/pipeline";

function makeStatus(
  overrides: Partial<OrchestratorStatus> = {},
): OrchestratorStatus {
  return {
    status: "stopped",
    project_id: "proj-1",
    current_batch: null,
    active_sessions: null,
    flagged_tasks: null,
    ...overrides,
  };
}

describe("OrchestratorStatusBar", () => {
  it("renders running state with green accent", () => {
    render(<OrchestratorStatusBar status={makeStatus({ status: "running" })} />);

    const bar = screen.getByTestId("orchestrator-status-bar");
    expect(bar.className).toContain("bg-green-900");
    expect(bar.className).toContain("border-green-700");

    expect(screen.getByTestId("orchestrator-status-text").textContent).toBe(
      "Orchestrator: Running",
    );

    const dot = screen.getByTestId("orchestrator-status-dot");
    expect(dot.className).toContain("bg-green-400");
  });

  it("renders stopped state with muted/gray style", () => {
    render(
      <OrchestratorStatusBar status={makeStatus({ status: "stopped" })} />,
    );

    const bar = screen.getByTestId("orchestrator-status-bar");
    expect(bar.className).toContain("bg-gray-800");
    expect(bar.className).toContain("border-gray-700");

    expect(screen.getByTestId("orchestrator-status-text").textContent).toBe(
      "Orchestrator: Stopped",
    );

    const dot = screen.getByTestId("orchestrator-status-dot");
    expect(dot.className).toContain("bg-gray-500");
  });

  it("shows flagged warning when flagged tasks > 0", () => {
    render(
      <OrchestratorStatusBar
        status={makeStatus({
          status: "running",
          flagged_tasks: ["t1", "t2"],
        })}
      />,
    );

    const warning = screen.getByTestId("orchestrator-flagged-warning");
    expect(warning.textContent).toBe("2 flagged");
  });

  it("does not show flagged warning when no flagged tasks", () => {
    render(
      <OrchestratorStatusBar
        status={makeStatus({ status: "running", flagged_tasks: [] })}
      />,
    );

    expect(
      screen.queryByTestId("orchestrator-flagged-warning"),
    ).not.toBeInTheDocument();
  });

  it("shows batch and session counts", () => {
    render(
      <OrchestratorStatusBar
        status={makeStatus({
          status: "running",
          current_batch: ["t1", "t2", "t3"],
          active_sessions: ["s1"],
        })}
      />,
    );

    expect(screen.getByText("Batch: 3 tasks")).toBeInTheDocument();
    expect(screen.getByText("Sessions: 1")).toBeInTheDocument();
  });
});
