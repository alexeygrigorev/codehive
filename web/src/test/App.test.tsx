import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { Routes, Route } from "react-router-dom";
import MainLayout from "@/layouts/MainLayout";
import DashboardPage from "@/pages/DashboardPage";
import ProjectPage from "@/pages/ProjectPage";
import SessionPage from "@/pages/SessionPage";
import NotFoundPage from "@/pages/NotFoundPage";

function renderWithRouter(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/sessions/:sessionId" element={<SessionPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("App routing", () => {
  it("renders DashboardPage at /", () => {
    renderWithRouter("/");
    expect(screen.getByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
  });

  it("renders ProjectPage at /projects/:projectId", () => {
    renderWithRouter("/projects/abc-123");
    expect(screen.getByRole("heading", { name: /project/i })).toBeInTheDocument();
    // ProjectPage now fetches data asynchronously, so it shows loading state initially
    expect(screen.getByText(/loading project/i)).toBeInTheDocument();
  });

  it("renders SessionPage at /sessions/:sessionId", () => {
    renderWithRouter("/sessions/xyz-789");
    expect(screen.getByRole("heading", { name: /session/i })).toBeInTheDocument();
    expect(screen.getByText(/xyz-789/)).toBeInTheDocument();
  });

  it("renders NotFoundPage for unknown routes", () => {
    renderWithRouter("/nonexistent-path");
    expect(screen.getByText(/404/)).toBeInTheDocument();
    expect(screen.getByText(/not found/i)).toBeInTheDocument();
  });
});

describe("MainLayout", () => {
  it("renders sidebar with Dashboard navigation link", () => {
    renderWithRouter("/");
    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    expect(dashboardLink).toBeInTheDocument();
    expect(dashboardLink).toHaveAttribute("href", "/");
  });

  it("renders an outlet area with child content", () => {
    renderWithRouter("/");
    // MainLayout's Outlet renders DashboardPage
    expect(screen.getByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
    // The main content area exists
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
});
