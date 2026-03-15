import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import DashboardPage from "@/pages/DashboardPage";

// Mock API modules
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

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockFetchProjects.mockReturnValue(new Promise(() => {})); // never resolves
    renderDashboard();
    expect(screen.getByText("Loading projects...")).toBeInTheDocument();
  });

  it("fetches projects and renders ProjectCard for each", async () => {
    const projects = [
      {
        id: "p1",
        workspace_id: "w1",
        name: "Project Alpha",
        path: "/tmp/alpha",
        description: "First project",
        archetype: "web",
        knowledge: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "p2",
        workspace_id: "w1",
        name: "Project Beta",
        path: "/tmp/beta",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-01-02T00:00:00Z",
      },
    ];
    mockFetchProjects.mockResolvedValue(projects);
    mockFetchSessions.mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });
    expect(screen.getByText("Project Beta")).toBeInTheDocument();
  });

  it("shows empty state when API returns empty array", async () => {
    mockFetchProjects.mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText(/no projects yet/i),
      ).toBeInTheDocument();
    });
  });

  it("shows error state when API call fails", async () => {
    mockFetchProjects.mockRejectedValue(
      new Error("Failed to fetch projects: 500"),
    );

    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch projects: 500"),
      ).toBeInTheDocument();
    });
  });

  it("each ProjectCard links to /projects/{id}", async () => {
    const projects = [
      {
        id: "p1",
        workspace_id: "w1",
        name: "Linked Project",
        path: "/tmp/p",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    mockFetchProjects.mockResolvedValue(projects);
    mockFetchSessions.mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Linked Project")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /linked project/i });
    expect(link).toHaveAttribute("href", "/projects/p1");
  });
});
