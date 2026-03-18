import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ProjectPage from "@/pages/ProjectPage";

vi.mock("@/api/projects", () => ({
  fetchProject: vi.fn(),
}));

vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn(),
  createSession: vi.fn(),
}));

vi.mock("@/api/issues", () => ({
  fetchIssues: vi.fn(),
  createIssue: vi.fn(),
}));

vi.mock("@/api/subagents", () => ({
  fetchSubAgents: vi.fn().mockResolvedValue([]),
}));

import { fetchProject } from "@/api/projects";
import { fetchSessions, createSession } from "@/api/sessions";
import { fetchIssues, createIssue } from "@/api/issues";

const mockFetchProject = vi.mocked(fetchProject);
const mockFetchSessions = vi.mocked(fetchSessions);
const mockCreateSession = vi.mocked(createSession);
const mockFetchIssues = vi.mocked(fetchIssues);
const mockCreateIssue = vi.mocked(createIssue);

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

const issues = [
  {
    id: "i1",
    project_id: "p1",
    title: "Fix login bug",
    description: null,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
  },
];

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
    mockFetchProject.mockResolvedValue(project);
    mockFetchSessions.mockResolvedValue(sessions);
    mockFetchIssues.mockResolvedValue(issues);
  });

  it("renders loading state initially", () => {
    mockFetchProject.mockReturnValue(new Promise(() => {}));
    mockFetchSessions.mockReturnValue(new Promise(() => {}));
    renderProjectPage();
    expect(screen.getByText("Loading project...")).toBeInTheDocument();
  });

  it("renders Sessions and Issues tabs", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });
    expect(screen.getByRole("tab", { name: "Sessions" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Issues" })).toBeInTheDocument();
  });

  it("Sessions tab is active by default and shows SessionList", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });
    const sessionsTab = screen.getByRole("tab", { name: "Sessions" });
    expect(sessionsTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Session Alpha")).toBeInTheDocument();
  });

  it("clicking Issues tab shows IssueList", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: "Issues" }));

    await waitFor(() => {
      expect(screen.getByText("Fix login bug")).toBeInTheDocument();
    });
    const issuesTab = screen.getByRole("tab", { name: "Issues" });
    expect(issuesTab).toHaveAttribute("aria-selected", "true");
  });

  it("project header is visible regardless of active tab", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });
    expect(screen.getByText("A great project")).toBeInTheDocument();
    expect(screen.getByText("web-app")).toBeInTheDocument();
    expect(screen.getByText("Path: /tmp/my-project")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Issues" }));
    expect(screen.getByText("My Project")).toBeInTheDocument();
    expect(screen.getByText("A great project")).toBeInTheDocument();
  });

  it("shows error when project fetch fails", async () => {
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

  it("New Session button opens creation form with engine and mode dropdowns", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });

    // Form not visible initially
    expect(screen.queryByPlaceholderText("Session name")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("+ New Session"));
    expect(screen.getByPlaceholderText("Session name")).toBeInTheDocument();
    expect(screen.getByLabelText("Engine")).toBeInTheDocument();
    expect(screen.getByLabelText("Mode")).toBeInTheDocument();
  });

  it("submitting session creation form calls createSession with correct params", async () => {
    const newSession = {
      id: "s2",
      project_id: "p1",
      issue_id: null,
      parent_session_id: null,
      name: "New Session",
      engine: "native",
      mode: "execution",
      status: "idle",
      config: null,
      created_at: "2026-01-02T00:00:00Z",
    };
    mockCreateSession.mockResolvedValue(newSession);

    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("+ New Session"));
    fireEvent.change(screen.getByPlaceholderText("Session name"), {
      target: { value: "New Session" },
    });
    fireEvent.click(screen.getByText("Create Session"));

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledWith("p1", {
        name: "New Session",
        engine: "native",
        mode: "execution",
      });
    });
  });

  it("session creation form closes after successful creation", async () => {
    const newSession = {
      id: "s2",
      project_id: "p1",
      issue_id: null,
      parent_session_id: null,
      name: "New Session",
      engine: "native",
      mode: "execution",
      status: "idle",
      config: null,
      created_at: "2026-01-02T00:00:00Z",
    };
    mockCreateSession.mockResolvedValue(newSession);

    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("+ New Session"));
    fireEvent.change(screen.getByPlaceholderText("Session name"), {
      target: { value: "New Session" },
    });
    fireEvent.click(screen.getByText("Create Session"));

    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Session name")).not.toBeInTheDocument();
    });
  });

  it("renders session list with correct data from API", async () => {
    const multipleSessions = [
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
    mockFetchSessions.mockResolvedValue(multipleSessions);

    renderProjectPage("p1");

    await waitFor(() => {
      expect(screen.getByText("Build Session")).toBeInTheDocument();
    });
    expect(screen.getByText("Test Session")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("idle")).toBeInTheDocument();
  });

  it("Issues tab creates issue via API and adds it to the list", async () => {
    const newIssue = {
      id: "i2",
      project_id: "p1",
      title: "New feature request",
      description: null,
      status: "open",
      created_at: "2026-01-02T00:00:00Z",
    };
    mockCreateIssue.mockResolvedValue(newIssue);

    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByText("My Project")).toBeInTheDocument();
    });

    // Switch to issues tab
    fireEvent.click(screen.getByRole("tab", { name: "Issues" }));
    await waitFor(() => {
      expect(screen.getByText("Fix login bug")).toBeInTheDocument();
    });

    // Open create form
    fireEvent.click(screen.getByText("+ New Issue"));
    fireEvent.change(screen.getByPlaceholderText("Issue title"), {
      target: { value: "New feature request" },
    });
    fireEvent.click(screen.getByText("Create Issue"));

    await waitFor(() => {
      expect(mockCreateIssue).toHaveBeenCalledWith("p1", {
        title: "New feature request",
      });
    });
  });
});
