import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import TaskCard, { timeAgo } from "@/components/pipeline/TaskCard";
import type { PipelineTask } from "@/api/pipeline";

function makeTask(overrides: Partial<PipelineTask> = {}): PipelineTask {
  return {
    id: "t1",
    session_id: "s1",
    title: "Fix login timeout",
    instructions: null,
    status: "pending",
    pipeline_status: "implementing",
    priority: 0,
    depends_on: null,
    mode: "auto",
    created_by: "user",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("TaskCard", () => {
  it("renders the task title", () => {
    render(<TaskCard task={makeTask()} />);
    expect(screen.getByText("Fix login timeout")).toBeInTheDocument();
  });

  it("renders the pipeline status badge", () => {
    render(<TaskCard task={makeTask()} />);
    expect(screen.getByTestId("task-status-badge").textContent).toBe(
      "implementing",
    );
  });

  it("renders relative time", () => {
    // 5 minutes ago
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    render(<TaskCard task={makeTask({ created_at: fiveMinAgo })} />);
    expect(screen.getByTestId("task-time-ago").textContent).toBe("5m ago");
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    const task = makeTask();
    render(<TaskCard task={task} onClick={onClick} />);
    fireEvent.click(screen.getByTestId("task-card-t1"));
    expect(onClick).toHaveBeenCalledWith(task);
  });
});

describe("timeAgo", () => {
  it("returns seconds for < 60 seconds", () => {
    const now = new Date(Date.now() - 30 * 1000).toISOString();
    expect(timeAgo(now)).toBe("30s ago");
  });

  it("returns minutes for < 60 minutes", () => {
    const now = new Date(Date.now() - 10 * 60 * 1000).toISOString();
    expect(timeAgo(now)).toBe("10m ago");
  });

  it("returns hours for < 24 hours", () => {
    const now = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(now)).toBe("3h ago");
  });

  it("returns days for >= 24 hours", () => {
    const now = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(now)).toBe("2d ago");
  });
});
