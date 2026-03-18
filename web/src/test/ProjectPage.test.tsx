import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ProjectPage from "@/pages/ProjectPage";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/api/projects", () => ({
  fetchProject: vi.fn(),
}));

vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn(),
  createSession: vi.fn(),
  updateSession: vi.fn(),
}));

vi.mock("@/api/issues", () => ({
  fetchIssues: vi.fn(),
  createIssue: vi.fn(),
}));

vi.mock("@/api/providers", () => ({
  fetchProviders: vi.fn(),
}));

vi.mock("@/api/subagents", () => ({
  fetchSubAgents: vi.fn().mockResolvedValue([]),
}));

import { fetchProject } from "@/api/projects";
import { fetchSessions, createSession } from "@/api/sessions";
import { fetchIssues, createIssue } from "@/api/issues";
import { fetchProviders } from "@/api/providers";

const mockFetchProject = vi.mocked(fetchProject);
const mockFetchSessions = vi.mocked(fetchSessions);
const mockCreateSession = vi.mocked(createSession);
const mockFetchIssues = vi.mocked(fetchIssues);
const mockCreateIssue = vi.mocked(createIssue);
const mockFetchProviders = vi.mocked(fetchProviders);

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
  const defaultProviders = [
    {
      name: "anthropic",
      base_url: "https://api.anthropic.com",
      api_key_set: true,
      default_model: "claude-sonnet-4-20250514",
    },
    {
      name: "zai",
      base_url: "https://api.z.ai/api/anthropic",
      api_key_set: true,
      default_model: "glm-4.7",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchProject.mockResolvedValue(project);
    mockFetchSessions.mockResolvedValue(sessions);
    mockFetchIssues.mockResolvedValue(issues);
    mockFetchProviders.mockResolvedValue(defaultProviders);
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
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });
    expect(screen.getByRole("tab", { name: "Sessions" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Issues" })).toBeInTheDocument();
  });

  it("Sessions tab is active by default and shows SessionList", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });
    const sessionsTab = screen.getByRole("tab", { name: "Sessions" });
    expect(sessionsTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Session Alpha")).toBeInTheDocument();
  });

  it("clicking Issues tab shows IssueList", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
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
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });
    expect(screen.getByText("A great project")).toBeInTheDocument();
    expect(screen.getByText("web-app")).toBeInTheDocument();
    expect(screen.getByText("Path: /tmp/my-project")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Issues" }));
    expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
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

  it("clicking + New Session opens dialog, submit creates session and navigates", async () => {
    const newSession = {
      id: "s-new",
      project_id: "p1",
      issue_id: null,
      parent_session_id: null,
      name: "New Session",
      engine: "native",
      mode: "execution",
      status: "idle",
      config: { provider: "anthropic", model: "claude-sonnet-4-20250514" },
      created_at: "2026-01-02T00:00:00Z",
    };
    mockCreateSession.mockResolvedValue(newSession);

    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });

    // Click opens dialog
    fireEvent.click(screen.getByText("+ New Session"));
    await waitFor(() => {
      expect(screen.getByTestId("new-session-dialog")).toBeInTheDocument();
    });

    // Submit the dialog (default values)
    fireEvent.click(screen.getByTestId("create-session-btn"));

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledWith("p1", {
        name: "New Session",
        engine: "native",
        mode: "execution",
        config: { provider: "anthropic", model: "claude-sonnet-4-20250514" },
      });
    });
    expect(mockNavigate).toHaveBeenCalledWith("/sessions/s-new");
  });

  it("Create button in dialog is disabled while creating", async () => {
    let resolveCreate: (value: unknown) => void;
    mockCreateSession.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );

    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });

    // Open dialog
    fireEvent.click(screen.getByText("+ New Session"));
    await waitFor(() => {
      expect(screen.getByTestId("new-session-dialog")).toBeInTheDocument();
    });

    // Submit
    fireEvent.click(screen.getByTestId("create-session-btn"));

    await waitFor(() => {
      const button = screen.getByTestId("create-session-btn");
      expect(button).toBeDisabled();
      expect(button).toHaveTextContent("Creating...");
    });

    // Resolve to clean up
    resolveCreate!({
      id: "s-new",
      project_id: "p1",
      issue_id: null,
      parent_session_id: null,
      name: "New Session",
      engine: "native",
      mode: "execution",
      status: "idle",
      config: null,
      created_at: "2026-01-02T00:00:00Z",
    });
  });

  it("shows error when session creation fails", async () => {
    mockCreateSession.mockRejectedValue(new Error("Server error"));

    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });

    // Open dialog and submit
    fireEvent.click(screen.getByText("+ New Session"));
    await waitFor(() => {
      expect(screen.getByTestId("new-session-dialog")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("create-session-btn"));

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  it("no session creation form elements exist on the page", async () => {
    renderProjectPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
    });

    expect(screen.queryByPlaceholderText("Session name")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Engine")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Mode")).not.toBeInTheDocument();
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
      expect(screen.getByRole("heading", { name: "My Project" })).toBeInTheDocument();
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
