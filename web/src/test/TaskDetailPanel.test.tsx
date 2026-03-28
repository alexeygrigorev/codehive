import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import TaskDetailPanel from "@/components/pipeline/TaskDetailPanel";
import type { PipelineTask } from "@/api/pipeline";

vi.mock("@/api/pipeline", () => ({
  fetchTaskPipelineLog: vi.fn(),
  fetchIssueLogEntries: vi.fn(),
}));

import {
  fetchTaskPipelineLog,
  fetchIssueLogEntries,
} from "@/api/pipeline";

const mockFetchTaskPipelineLog = vi.mocked(fetchTaskPipelineLog);
const mockFetchIssueLogEntries = vi.mocked(fetchIssueLogEntries);

function makeTask(overrides: Partial<PipelineTask> = {}): PipelineTask {
  return {
    id: "task-1",
    session_id: "sess-1",
    title: "Test Task",
    instructions: null,
    status: "pending",
    pipeline_status: "implementing",
    priority: 0,
    depends_on: null,
    mode: "auto",
    created_by: "user",
    created_at: "2026-01-01T00:00:00Z",
    issue_id: null,
    ...overrides,
  };
}

describe("TaskDetailPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchTaskPipelineLog.mockResolvedValue([]);
  });

  it("renders task details and pipeline history", async () => {
    mockFetchTaskPipelineLog.mockResolvedValue([
      {
        id: "log-1",
        task_id: "task-1",
        from_status: "backlog",
        to_status: "implementing",
        actor: "orchestrator",
        created_at: "2026-01-01T01:00:00Z",
      },
    ]);

    const task = makeTask();
    render(<TaskDetailPanel task={task} onClose={() => {}} />);

    expect(screen.getByText("Test Task")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/backlog/)).toBeInTheDocument();
    });
    // "implementing" appears in both the status badge and the log entry
    expect(screen.getAllByText(/implementing/).length).toBeGreaterThanOrEqual(1);
  });

  it("does not render issue log section when task has no issue_id", async () => {
    const task = makeTask({ issue_id: null });
    render(<TaskDetailPanel task={task} onClose={() => {}} />);

    await waitFor(() => {
      expect(mockFetchTaskPipelineLog).toHaveBeenCalled();
    });

    expect(screen.queryByTestId("issue-log-section")).not.toBeInTheDocument();
    expect(mockFetchIssueLogEntries).not.toHaveBeenCalled();
  });

  it("fetches and displays issue log entries when task has a linked issue", async () => {
    mockFetchIssueLogEntries.mockResolvedValue([
      {
        id: "ilog-1",
        issue_id: "issue-42",
        agent_role: "SWE",
        content: "Implemented the login feature",
        created_at: "2026-01-02T10:00:00Z",
      },
      {
        id: "ilog-2",
        issue_id: "issue-42",
        agent_role: "QA",
        content: "All tests passing, VERDICT: PASS",
        created_at: "2026-01-02T11:00:00Z",
      },
    ]);

    const task = makeTask({ issue_id: "issue-42" });
    render(<TaskDetailPanel task={task} onClose={() => {}} />);

    await waitFor(() => {
      expect(mockFetchIssueLogEntries).toHaveBeenCalledWith("issue-42");
    });

    await waitFor(() => {
      expect(screen.getByText("Issue Log")).toBeInTheDocument();
    });

    const entries = screen.getAllByTestId("issue-log-entry");
    expect(entries).toHaveLength(2);
    expect(
      screen.getByText("Implemented the login feature"),
    ).toBeInTheDocument();
    expect(screen.getByText("[SWE]")).toBeInTheDocument();
    expect(
      screen.getByText("All tests passing, VERDICT: PASS"),
    ).toBeInTheDocument();
    expect(screen.getByText("[QA]")).toBeInTheDocument();
  });

  it("shows empty state when issue has no log entries", async () => {
    mockFetchIssueLogEntries.mockResolvedValue([]);

    const task = makeTask({ issue_id: "issue-99" });
    render(<TaskDetailPanel task={task} onClose={() => {}} />);

    await waitFor(() => {
      expect(mockFetchIssueLogEntries).toHaveBeenCalledWith("issue-99");
    });

    await waitFor(() => {
      expect(screen.getByText("No issue log entries")).toBeInTheDocument();
    });
  });
});
