import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import ProjectCard from "@/components/ProjectCard";

function renderCard(props: Partial<Parameters<typeof ProjectCard>[0]> = {}) {
  const defaults = {
    id: "p1",
    name: "Test Project",
    description: "A test project description",
    archetype: null as string | null,
    sessionCount: 0,
  };
  return render(
    <MemoryRouter>
      <ProjectCard {...defaults} {...props} />
    </MemoryRouter>,
  );
}

describe("ProjectCard", () => {
  it("renders project name and description", () => {
    renderCard({ name: "My Project", description: "Some description" });
    expect(screen.getByText("My Project")).toBeInTheDocument();
    expect(screen.getByText("Some description")).toBeInTheDocument();
  });

  it("renders archetype badge when archetype is set", () => {
    renderCard({ archetype: "web-app" });
    expect(screen.getByText("web-app")).toBeInTheDocument();
  });

  it("does not render archetype badge when archetype is null", () => {
    renderCard({ archetype: null });
    expect(screen.queryByText("web-app")).not.toBeInTheDocument();
  });

  it("links to the correct /projects/{id} route", () => {
    renderCard({ id: "abc-123" });
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/projects/abc-123");
  });

  it("displays session count", () => {
    renderCard({ sessionCount: 5 });
    expect(screen.getByText("5 sessions")).toBeInTheDocument();
  });

  it("displays singular session when count is 1", () => {
    renderCard({ sessionCount: 1 });
    expect(screen.getByText("1 session")).toBeInTheDocument();
  });

  it("truncates long descriptions", () => {
    const longDesc = "A".repeat(150);
    renderCard({ description: longDesc });
    expect(screen.getByText("A".repeat(120) + "...")).toBeInTheDocument();
  });
});
