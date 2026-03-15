import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import TodoPanel from "@/components/sidebar/TodoPanel";

vi.mock("@/api/tasks", () => ({
  fetchTasks: vi.fn(),
}));

import { fetchTasks } from "@/api/tasks";
const mockFetchTasks = vi.mocked(fetchTasks);

const mockTasks = [
  {
    id: "t1",
    session_id: "s1",
    title: "Task A",
    instructions: "",
    status: "done",
    priority: 1,
    depends_on: [],
    mode: "execution",
    created_by: "agent",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "t2",
    session_id: "s1",
    title: "Task B",
    instructions: "",
    status: "running",
    priority: 2,
    depends_on: [],
    mode: "execution",
    created_by: "agent",
    created_at: "2026-01-01T00:01:00Z",
  },
  {
    id: "t3",
    session_id: "s1",
    title: "Task C",
    instructions: "",
    status: "pending",
    priority: 3,
    depends_on: [],
    mode: "execution",
    created_by: "agent",
    created_at: "2026-01-01T00:02:00Z",
  },
  {
    id: "t4",
    session_id: "s1",
    title: "Task D",
    instructions: "",
    status: "failed",
    priority: 4,
    depends_on: [],
    mode: "execution",
    created_by: "agent",
    created_at: "2026-01-01T00:03:00Z",
  },
  {
    id: "t5",
    session_id: "s1",
    title: "Task E",
    instructions: "",
    status: "blocked",
    priority: 5,
    depends_on: [],
    mode: "execution",
    created_by: "agent",
    created_at: "2026-01-01T00:04:00Z",
  },
];

describe("TodoPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while tasks are being fetched", () => {
    mockFetchTasks.mockReturnValue(new Promise(() => {}));
    render(<TodoPanel sessionId="s1" />);
    expect(screen.getByText("Loading tasks...")).toBeInTheDocument();
  });

  it("renders a list of tasks with title and status", async () => {
    mockFetchTasks.mockResolvedValue(mockTasks);
    render(<TodoPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("Task A")).toBeInTheDocument();
    });
    expect(screen.getByText("Task B")).toBeInTheDocument();
    expect(screen.getByText("Task C")).toBeInTheDocument();
  });

  it("shows correct status indicator for each status value", async () => {
    mockFetchTasks.mockResolvedValue(mockTasks);
    render(<TodoPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("Task A")).toBeInTheDocument();
    });

    const indicators = document.querySelectorAll(".task-status-indicator");
    const statuses = Array.from(indicators).map((el) =>
      el.getAttribute("data-status"),
    );
    expect(statuses).toContain("done");
    expect(statuses).toContain("running");
    expect(statuses).toContain("pending");
    expect(statuses).toContain("failed");
    expect(statuses).toContain("blocked");
  });

  it("displays progress summary text", async () => {
    mockFetchTasks.mockResolvedValue(mockTasks);
    render(<TodoPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("1/5 done")).toBeInTheDocument();
    });
  });

  it("shows empty state when task list is empty", async () => {
    mockFetchTasks.mockResolvedValue([]);
    render(<TodoPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("No tasks yet")).toBeInTheDocument();
    });
  });

  it("shows error state when fetch fails", async () => {
    mockFetchTasks.mockRejectedValue(new Error("Failed to fetch tasks: 500"));
    render(<TodoPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch tasks: 500"),
      ).toBeInTheDocument();
    });
  });
});
