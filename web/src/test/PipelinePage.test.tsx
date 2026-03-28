import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import PipelinePage from "@/pages/PipelinePage";

vi.mock("@/api/projects", () => ({
  fetchProjects: vi.fn(),
}));

vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn(),
}));

vi.mock("@/api/issues", () => ({
  fetchIssues: vi.fn(),
}));

vi.mock("@/api/pipeline", () => ({
  fetchSessionTasks: vi.fn(),
  fetchOrchestratorStatus: vi.fn(),
  fetchTaskPipelineLog: vi.fn(),
  addTask: vi.fn(),
}));

import { fetchProjects } from "@/api/projects";
import { fetchSessions } from "@/api/sessions";
import { fetchIssues } from "@/api/issues";
import {
  fetchSessionTasks,
  fetchOrchestratorStatus,
} from "@/api/pipeline";

const mockFetchProjects = vi.mocked(fetchProjects);
const mockFetchSessions = vi.mocked(fetchSessions);
const mockFetchIssues = vi.mocked(fetchIssues);
const mockFetchSessionTasks = vi.mocked(fetchSessionTasks);
const mockFetchOrchestratorStatus = vi.mocked(fetchOrchestratorStatus);

function renderPipeline() {
  return render(
    <MemoryRouter>
      <PipelinePage />
    </MemoryRouter>,
  );
}

describe("PipelinePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the pipeline page with kanban board populated from API", async () => {
    mockFetchProjects.mockResolvedValue([
      {
        id: "proj-1",
        name: "My Project",
        path: "/tmp/proj",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockFetchIssues.mockResolvedValue([]);
    mockFetchSessions.mockResolvedValue([
      {
        id: "sess-1",
        project_id: "proj-1",
        issue_id: null,
        parent_session_id: null,
        name: "orch",
        engine: "claude_code",
        mode: "orchestrator",
        status: "active",
        config: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockFetchSessionTasks.mockResolvedValue([
      {
        id: "t1",
        session_id: "sess-1",
        title: "Build login",
        instructions: null,
        status: "pending",
        pipeline_status: "implementing",
        priority: 0,
        depends_on: null,
        mode: "auto",
        created_by: "user",
        created_at: "2026-01-01T00:00:00Z",
        issue_id: null,
      },
      {
        id: "t2",
        session_id: "sess-1",
        title: "Fix navbar",
        instructions: null,
        status: "pending",
        pipeline_status: "backlog",
        priority: 0,
        depends_on: null,
        mode: "auto",
        created_by: "user",
        created_at: "2026-01-01T00:00:00Z",
        issue_id: null,
      },
    ]);
    mockFetchOrchestratorStatus.mockResolvedValue({
      status: "running",
      project_id: "proj-1",
      current_batch: ["t1"],
      active_sessions: ["sess-1"],
      flagged_tasks: [],
    });

    renderPipeline();

    await waitFor(() => {
      expect(screen.getByText("Build login")).toBeInTheDocument();
    });
    expect(screen.getByText("Fix navbar")).toBeInTheDocument();
    expect(screen.getByTestId("kanban-board")).toBeInTheDocument();
    expect(
      screen.getByTestId("column-count-implementing").textContent,
    ).toBe("1");
    expect(screen.getByTestId("column-count-backlog").textContent).toBe("1");
  });

  it("shows loading state initially", () => {
    mockFetchProjects.mockReturnValue(new Promise(() => {}));
    renderPipeline();
    expect(
      screen.getByText("Loading pipeline data..."),
    ).toBeInTheDocument();
  });

  it("triggers polling after interval", async () => {
    mockFetchProjects.mockResolvedValue([
      {
        id: "proj-1",
        name: "My Project",
        path: "/tmp/proj",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    mockFetchIssues.mockResolvedValue([]);
    mockFetchSessions.mockResolvedValue([]);
    mockFetchSessionTasks.mockResolvedValue([]);
    mockFetchOrchestratorStatus.mockResolvedValue({
      status: "stopped",
      project_id: "proj-1",
      current_batch: null,
      active_sessions: null,
      flagged_tasks: null,
    });

    renderPipeline();

    await waitFor(() => {
      expect(mockFetchSessions).toHaveBeenCalledTimes(1);
    });

    // Advance time by 10 seconds to trigger the poll
    vi.advanceTimersByTime(10_000);

    await waitFor(() => {
      expect(mockFetchSessions).toHaveBeenCalledTimes(2);
    });
  });
});
