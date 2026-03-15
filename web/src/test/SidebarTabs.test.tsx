import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import SidebarTabs from "@/components/sidebar/SidebarTabs";

// Mock all panel components to isolate SidebarTabs
vi.mock("@/components/sidebar/TodoPanel", () => ({
  default: () => <div data-testid="todo-panel">TodoPanel</div>,
}));
vi.mock("@/components/sidebar/ChangedFilesPanel", () => ({
  default: () => (
    <div data-testid="changed-files-panel">ChangedFilesPanel</div>
  ),
}));
vi.mock("@/components/sidebar/TimelinePanel", () => ({
  default: () => <div data-testid="timeline-panel">TimelinePanel</div>,
}));
vi.mock("@/components/sidebar/SubAgentPanel", () => ({
  default: () => <div data-testid="sub-agent-panel">SubAgentPanel</div>,
}));

describe("SidebarTabs", () => {
  it("renders all four tab labels", () => {
    render(<SidebarTabs sessionId="s1" />);

    expect(screen.getByText("ToDo")).toBeInTheDocument();
    expect(screen.getByText("Changed Files")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Sub-agents")).toBeInTheDocument();
  });

  it("defaults to the ToDo tab being selected", () => {
    render(<SidebarTabs sessionId="s1" />);

    const todoTab = screen.getByText("ToDo");
    expect(todoTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("todo-panel")).toBeInTheDocument();
  });

  it("clicking a different tab fires onTabChange callback with the correct key", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<SidebarTabs sessionId="s1" onTabChange={onTabChange} />);

    await user.click(screen.getByText("Timeline"));

    expect(onTabChange).toHaveBeenCalledWith("timeline");
  });

  it("clicking a tab switches the visible panel", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    // Initially shows TodoPanel
    expect(screen.getByTestId("todo-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("changed-files-panel")).not.toBeInTheDocument();

    // Click Changed Files
    await user.click(screen.getByText("Changed Files"));

    expect(screen.queryByTestId("todo-panel")).not.toBeInTheDocument();
    expect(screen.getByTestId("changed-files-panel")).toBeInTheDocument();
  });

  it("the active tab has a distinct CSS class", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    const todoTab = screen.getByText("ToDo");
    expect(todoTab.className).toContain("sidebar-tab-active");

    await user.click(screen.getByText("Timeline"));

    expect(todoTab.className).not.toContain("sidebar-tab-active");
    expect(screen.getByText("Timeline").className).toContain(
      "sidebar-tab-active",
    );
  });
});
