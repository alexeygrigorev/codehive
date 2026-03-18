import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import Breadcrumb from "@/components/Breadcrumb";

function renderBreadcrumb(
  segments: { label: string; to: string }[],
) {
  return render(
    <MemoryRouter>
      <Breadcrumb segments={segments} />
    </MemoryRouter>,
  );
}

describe("Breadcrumb", () => {
  it("renders nothing when given empty segments", () => {
    const { container } = renderBreadcrumb([]);
    expect(container.innerHTML).toBe("");
  });

  it("renders single segment (project page): Dashboard > Project Name", () => {
    renderBreadcrumb([
      { label: "Dashboard", to: "/" },
      { label: "My Project", to: "/projects/p1" },
    ]);

    const dashboardLink = screen.getByRole("link", { name: "Dashboard" });
    expect(dashboardLink).toHaveAttribute("href", "/");

    // Last segment is plain text, not a link
    expect(screen.getByText("My Project")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My Project" })).not.toBeInTheDocument();
  });

  it("renders two segments (session page): Dashboard > Project > Session", () => {
    renderBreadcrumb([
      { label: "Dashboard", to: "/" },
      { label: "My Project", to: "/projects/p1" },
      { label: "Session Alpha", to: "/sessions/s1" },
    ]);

    const dashboardLink = screen.getByRole("link", { name: "Dashboard" });
    expect(dashboardLink).toHaveAttribute("href", "/");

    const projectLink = screen.getByRole("link", { name: "My Project" });
    expect(projectLink).toHaveAttribute("href", "/projects/p1");

    // Last segment is plain text
    expect(screen.getByText("Session Alpha")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Session Alpha" })).not.toBeInTheDocument();
  });

  it("current (last) segment has aria-current='page'", () => {
    renderBreadcrumb([
      { label: "Dashboard", to: "/" },
      { label: "Current Page", to: "/current" },
    ]);

    const current = screen.getByText("Current Page");
    expect(current).toHaveAttribute("aria-current", "page");
  });

  it("has separators between segments", () => {
    renderBreadcrumb([
      { label: "Dashboard", to: "/" },
      { label: "Project", to: "/projects/p1" },
      { label: "Session", to: "/sessions/s1" },
    ]);

    const separators = screen.getAllByText("/");
    expect(separators).toHaveLength(2);
  });
});
