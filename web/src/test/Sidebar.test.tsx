import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Sidebar from "@/components/Sidebar";

vi.mock("@/api/projects", () => ({
  fetchProjects: vi.fn(),
}));

import { fetchProjects } from "@/api/projects";

const mockFetchProjects = vi.mocked(fetchProjects);

const now = new Date();
const todayISO = now.toISOString();
const yesterdayDate = new Date(now);
yesterdayDate.setDate(yesterdayDate.getDate() - 1);
const yesterdayISO = yesterdayDate.toISOString();
const lastWeekDate = new Date(now);
lastWeekDate.setDate(lastWeekDate.getDate() - 5);
const lastWeekISO = lastWeekDate.toISOString();
const lastMonthDate = new Date(now);
lastMonthDate.setDate(lastMonthDate.getDate() - 20);
const lastMonthISO = lastMonthDate.toISOString();
const olderDate = new Date(now);
olderDate.setDate(olderDate.getDate() - 60);
const olderISO = olderDate.toISOString();

const projects = [
  {
    id: "p1",
    name: "Project Alpha",
    path: "/tmp/alpha",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: todayISO,
  },
  {
    id: "p2",
    name: "Project Beta",
    path: "/tmp/beta",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: yesterdayISO,
  },
  {
    id: "p3",
    name: "Project Gamma",
    path: "/tmp/gamma",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: lastWeekISO,
  },
  {
    id: "p4",
    name: "Project Delta",
    path: "/tmp/delta",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: lastMonthISO,
  },
  {
    id: "p5",
    name: "Project Epsilon",
    path: "/tmp/epsilon",
    description: null,
    archetype: null,
    knowledge: null,
    created_at: olderISO,
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
  });

  it("renders flat list of projects fetched from API", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });
    expect(screen.getByText("Project Beta")).toBeInTheDocument();
    expect(screen.getByText("Project Gamma")).toBeInTheDocument();
    expect(screen.getByText("Project Delta")).toBeInTheDocument();
    expect(screen.getByText("Project Epsilon")).toBeInTheDocument();
  });

  it("renders Dashboard and Usage links", () => {
    mockFetchProjects.mockResolvedValue([]);
    renderSidebar();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Usage")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Dashboard" });
    expect(link).toHaveAttribute("href", "/");
  });

  it("shows time group headers", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    expect(screen.getByText("Previous 7 days")).toBeInTheDocument();
    expect(screen.getByText("Previous 30 days")).toBeInTheDocument();
    expect(screen.getByText("Older")).toBeInTheDocument();
  });

  it("groups are collapsible", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    // Click "Today" group header to collapse
    fireEvent.click(screen.getByTestId("time-group-toggle-today"));

    // Alpha should be hidden
    expect(screen.queryByText("Project Alpha")).not.toBeInTheDocument();

    // Click again to expand
    fireEvent.click(screen.getByTestId("time-group-toggle-today"));

    expect(screen.getByText("Project Alpha")).toBeInTheDocument();
  });

  it("search filters projects by name in real time", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("sidebar-search");
    fireEvent.change(searchInput, { target: { value: "Alpha" } });

    expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Project Beta")).not.toBeInTheDocument();
    expect(screen.queryByText("Project Gamma")).not.toBeInTheDocument();
  });

  it("search updates project count to filtered count", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const countEl = screen.getByTestId("sidebar-project-count");
    expect(countEl.textContent).toBe("Projects (5)");

    const searchInput = screen.getByTestId("sidebar-search");
    fireEvent.change(searchInput, { target: { value: "Alpha" } });

    expect(countEl.textContent).toBe("Projects (1 of 5)");
  });

  it("empty time groups are hidden when search filters them out", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("sidebar-search");
    fireEvent.change(searchInput, { target: { value: "Alpha" } });

    // Only "Today" group should be visible (Alpha is today)
    expect(screen.getByTestId("time-group-today")).toBeInTheDocument();
    expect(screen.queryByTestId("time-group-yesterday")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("time-group-previous-7-days"),
    ).not.toBeInTheDocument();
  });

  it("active project is highlighted when on its page", async () => {
    renderSidebar("/projects/p1");

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const projectLink = screen.getByRole("link", { name: "Project Alpha" });
    expect(projectLink.className).toContain("font-medium");
    expect(projectLink.className).toContain("bg-gray-800");
  });

  it("New Project button navigates to /projects/new", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-new-project")).toBeInTheDocument();
    });

    const newProjectLink = screen.getByTestId("sidebar-new-project");
    expect(newProjectLink).toHaveAttribute("href", "/projects/new");
    expect(newProjectLink.textContent).toContain("New Project");
  });

  it("shows project count in header", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const countEl = screen.getByTestId("sidebar-project-count");
    expect(countEl.textContent).toBe("Projects (5)");
  });

  it("shows empty state when no projects exist", async () => {
    mockFetchProjects.mockResolvedValue([]);
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("No projects yet")).toBeInTheDocument();
    });
  });

  it("collapsed sidebar shows narrow width", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    });

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

  it("collapsed sidebar hides search input and time groups", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("sidebar-toggle"));

    expect(screen.queryByTestId("sidebar-search")).not.toBeInTheDocument();
    expect(screen.queryByTestId("time-group-today")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("sidebar-project-count"),
    ).not.toBeInTheDocument();
  });

  it("project links navigate to /projects/{id}", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    const link = screen.getByRole("link", { name: "Project Alpha" });
    expect(link).toHaveAttribute("href", "/projects/p1");
  });

  it("project list area has independent scroll", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    // The project list container should have overflow-y-auto
    const sidebar = screen.getByTestId("sidebar");
    const scrollContainer = sidebar.querySelector(".overflow-y-auto");
    expect(scrollContainer).toBeInTheDocument();
  });

  it("does not render sessions in the sidebar", async () => {
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    });

    // No session toggle buttons or session lists
    expect(screen.queryByTestId("toggle-p1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sessions-p1")).not.toBeInTheDocument();
  });
});
