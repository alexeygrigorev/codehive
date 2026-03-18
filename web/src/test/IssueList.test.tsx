import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import IssueList from "@/components/IssueList";
import type { IssueRead } from "@/api/issues";

function makeIssue(overrides: Partial<IssueRead> = {}): IssueRead {
  return {
    id: "i1",
    project_id: "p1",
    title: "Test Issue",
    description: null,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("IssueList", () => {
  it("renders list of issues with title, status badge, and created_at", () => {
    const issues = [
      makeIssue({ id: "i1", title: "Bug fix", status: "open" }),
      makeIssue({ id: "i2", title: "Feature", status: "in_progress" }),
      makeIssue({ id: "i3", title: "Done thing", status: "closed" }),
    ];
    render(
      <IssueList
        issues={issues}
        statusFilter={null}
        onFilterChange={vi.fn()}
        onCreateIssue={vi.fn()}
      />,
    );
    expect(screen.getByText("Bug fix")).toBeInTheDocument();
    expect(screen.getByText("Feature")).toBeInTheDocument();
    expect(screen.getByText("Done thing")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("in_progress")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
  });

  it("shows empty state message when no issues", () => {
    render(
      <IssueList
        issues={[]}
        statusFilter={null}
        onFilterChange={vi.fn()}
        onCreateIssue={vi.fn()}
      />,
    );
    expect(screen.getByText("No issues found.")).toBeInTheDocument();
  });

  it("status filter buttons highlight the active filter", () => {
    render(
      <IssueList
        issues={[]}
        statusFilter="open"
        onFilterChange={vi.fn()}
        onCreateIssue={vi.fn()}
      />,
    );
    const openBtn = screen.getByRole("button", { name: "Open" });
    const allBtn = screen.getByRole("button", { name: "All" });
    expect(openBtn.className).toContain("bg-blue-600");
    expect(allBtn.className).not.toContain("bg-blue-600");
  });

  it("clicking a filter calls the callback with the correct status value", () => {
    const onFilterChange = vi.fn();
    render(
      <IssueList
        issues={[]}
        statusFilter={null}
        onFilterChange={onFilterChange}
        onCreateIssue={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(onFilterChange).toHaveBeenCalledWith("open");

    fireEvent.click(screen.getByRole("button", { name: "In Progress" }));
    expect(onFilterChange).toHaveBeenCalledWith("in_progress");

    fireEvent.click(screen.getByRole("button", { name: "Closed" }));
    expect(onFilterChange).toHaveBeenCalledWith("closed");

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(onFilterChange).toHaveBeenCalledWith(null);
  });

  it("uses correct badge colors for each status", () => {
    const issues = [
      makeIssue({ id: "i1", title: "Open", status: "open" }),
      makeIssue({ id: "i2", title: "InProg", status: "in_progress" }),
      makeIssue({ id: "i3", title: "Closed", status: "closed" }),
    ];
    render(
      <IssueList
        issues={issues}
        statusFilter={null}
        onFilterChange={vi.fn()}
        onCreateIssue={vi.fn()}
      />,
    );
    // Find status badges (not the filter buttons)
    const openBadge = screen.getByText("open");
    const inProgressBadge = screen.getByText("in_progress");
    const closedBadge = screen.getByText("closed");
    expect(openBadge.className).toContain("bg-blue-100");
    expect(inProgressBadge.className).toContain("bg-yellow-100");
    expect(closedBadge.className).toContain("bg-green-100");
  });

  it("New Issue button shows create form and Cancel hides it", () => {
    render(
      <IssueList
        issues={[]}
        statusFilter={null}
        onFilterChange={vi.fn()}
        onCreateIssue={vi.fn()}
      />,
    );
    // Form not visible initially
    expect(screen.queryByPlaceholderText("Issue title")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("+ New Issue"));
    expect(screen.getByPlaceholderText("Issue title")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByPlaceholderText("Issue title")).not.toBeInTheDocument();
  });
});
