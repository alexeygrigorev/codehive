import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Sidebar from "@/components/Sidebar";

vi.mock("@/api/projects", () => ({
  fetchProjects: vi.fn(),
}));

vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn(),
}));

import { fetchProjects } from "@/api/projects";
import { fetchSessions } from "@/api/sessions";

const mockFetchProjects = vi.mocked(fetchProjects);
const mockFetchSessions = vi.mocked(fetchSessions);

const projects = [
  {
    id: "p1",
    name: "Project Alpha",
    path: "/tmp/alpha",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "p2",
    name: "Project Beta",
    path: "/tmp/beta",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: "2026-01-02T00:00:00Z",
  },
];

const sessionsP1 = [
  {
    id: "s1",
    project_id: "p1",
    issue_id: null,
    parent_session_id: null,
    name: "Session One",
    engine: "native",
    mode: "execution",
    status: "executing",
    config: null,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "s2",
    project_id: "p1",
    issue_id: null,
    parent_session_id: null,
    name: "Session Two",
    engine: "native",
    mode: "execution",
    status: "completed",
    config: null,
    created_at: "2026-01-02T00:00:00Z",
  },
];

function renderSidebar(initialPath: string = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockFetchProjects.mockResolvedValue(projects);
    mockFetchSessions.mockResolvedValue(sessionsP1);
  });

  it("renders list of projects fetched from API", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });
    expect(screen.getByText("Project Beta")).toBeInTheDocument();
  });

  it("renders Dashboard link", () => {
    mockFetchProjects.mockResolvedValue([]);
    renderSidebar();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Dashboard" });
    expect(link).toHaveAttribute("href", "/");
  });

  it("clicking expand toggle shows session list under the project", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    // Sessions not visible initially
    expect(screen.queryByText("Session One")).not.toBeInTheDocument();

    // Click toggle
    fireEvent.click(screen.getByTestId("toggle-p1"));

    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeInTheDocument();
    });
    expect(screen.getByText("Session Two")).toBeInTheDocument();
  });

  it("sessions show name and status dot", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-p1"));

    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeInTheDocument();
    });

    // Status dots should be present (aria-label = status)
    expect(screen.getByLabelText("executing")).toBeInTheDocument();
    expect(screen.getByLabelText("completed")).toBeInTheDocument();
  });

  it("does not re-fetch sessions on every toggle", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    // First expand
    fireEvent.click(screen.getByTestId("toggle-p1"));
    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeInTheDocument();
    });

    // Collapse
    fireEvent.click(screen.getByTestId("toggle-p1"));
    await waitFor(() => {
      expect(screen.queryByText("Session One")).not.toBeInTheDocument();
    });

    // Expand again
    fireEvent.click(screen.getByTestId("toggle-p1"));
    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeInTheDocument();
    });

    // fetchSessions should have been called only once for p1
    expect(mockFetchSessions).toHaveBeenCalledTimes(1);
    expect(mockFetchSessions).toHaveBeenCalledWith("p1");
  });

  it("active project is highlighted when on its page", async () => {
    renderSidebar("/projects/p1");

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const projectLink = screen.getByRole("link", { name: "Project Alpha" });
    expect(projectLink.className).toContain("font-medium");
  });

  it("active session is highlighted when on its page", async () => {
    renderSidebar("/sessions/s1");

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    // Expand project to see sessions
    fireEvent.click(screen.getByTestId("toggle-p1"));

    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeInTheDocument();
    });

    const sessionLink = screen.getByRole("link", { name: /Session One/ });
    expect(sessionLink.className).toContain("font-medium");
  });

  it("collapsed sidebar shows narrow width", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    });

    // Click collapse toggle
    fireEvent.click(screen.getByTestId("sidebar-toggle"));

    const sidebar = screen.getByTestId("sidebar");
    expect(sidebar.className).toContain("w-12");
  });

  it("collapse state persists in localStorage", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("sidebar-toggle"));

    expect(localStorage.getItem("codehive-sidebar-collapsed")).toBe("true");
  });

  it("restores collapsed state from localStorage", async () => {
    localStorage.setItem("codehive-sidebar-collapsed", "true");

    renderSidebar();

    const sidebar = screen.getByTestId("sidebar");
    expect(sidebar.className).toContain("w-12");
  });

  it("project links navigate to /projects/{id}", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const link = screen.getByRole("link", { name: "Project Alpha" });
    expect(link).toHaveAttribute("href", "/projects/p1");
  });

  it("session links navigate to /sessions/{id}", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-p1"));

    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeInTheDocument();
    });

    const link = screen.getByRole("link", { name: /Session One/ });
    expect(link).toHaveAttribute("href", "/sessions/s1");
  });
});
