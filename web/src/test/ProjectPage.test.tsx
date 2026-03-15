import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ProjectPage from "@/pages/ProjectPage";

vi.mock("@/api/projects", () => ({
  fetchProject: vi.fn(),
}));

vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn(),
}));

import { fetchProject } from "@/api/projects";
import { fetchSessions } from "@/api/sessions";

const mockFetchProject = vi.mocked(fetchProject);
const mockFetchSessions = vi.mocked(fetchSessions);

function renderProjectPage(projectId: string = "p1") {
  return render(
    <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProjectPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockFetchProject.mockReturnValue(new Promise(() => {}));
    mockFetchSessions.mockReturnValue(new Promise(() => {}));
    renderProjectPage();
    expect(screen.getByText("Loading project...")).toBeInTheDocument();
  });

  it("fetches project + sessions and renders header and SessionList", async () => {
    const project = {
      id: "p1",
      workspace_id: "w1",
      name: "My Project",
      path: "/tmp/my-project",
      description: "A great project",
      archetype: "web-app",
      knowledge: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    const sessions = [
      {
        id: "s1",
        project_id: "p1",
        issue_id: null,
        parent_session_id: null,
        name: "Session Alpha",
        engine: "claude",
        mode: "auto",
        status: "executing",
        config: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    mockFetchProject.mockResolvedValue(project);
    mockFetchSessions.mockResolvedValue(sessions);

    renderProjectPage("p1");

    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });
    expect(screen.getByText("A great project")).toBeInTheDocument();
    expect(screen.getByText("web-app")).toBeInTheDocument();
    expect(screen.getByText("Path: /tmp/my-project")).toBeInTheDocument();
    expect(screen.getByText("Session Alpha")).toBeInTheDocument();
    expect(screen.getByText("executing")).toBeInTheDocument();
  });

  it("shows error/not-found when project ID does not exist", async () => {
    mockFetchProject.mockRejectedValue(
      new Error("Failed to fetch project: 404"),
    );
    mockFetchSessions.mockRejectedValue(
      new Error("Failed to fetch sessions: 404"),
    );

    renderProjectPage("nonexistent");

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch project: 404"),
      ).toBeInTheDocument();
    });
  });

  it("renders session list with correct data from API", async () => {
    const project = {
      id: "p1",
      workspace_id: "w1",
      name: "Project",
      path: "/tmp/p",
      description: null,
      archetype: null,
      knowledge: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    const sessions = [
      {
        id: "s1",
        project_id: "p1",
        issue_id: null,
        parent_session_id: null,
        name: "Build Session",
        engine: "gpt4",
        mode: "manual",
        status: "completed",
        config: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "s2",
        project_id: "p1",
        issue_id: null,
        parent_session_id: null,
        name: "Test Session",
        engine: "claude",
        mode: "auto",
        status: "idle",
        config: null,
        created_at: "2026-01-02T00:00:00Z",
      },
    ];
    mockFetchProject.mockResolvedValue(project);
    mockFetchSessions.mockResolvedValue(sessions);

    renderProjectPage("p1");

    await waitFor(() => {
      expect(screen.getByText("Build Session")).toBeInTheDocument();
    });
    expect(screen.getByText("Test Session")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("idle")).toBeInTheDocument();
  });
});
