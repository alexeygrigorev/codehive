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
vi.mock("@/components/sidebar/ActivityPanel", () => ({
  default: () => <div data-testid="activity-panel">ActivityPanel</div>,
}));
vi.mock("@/components/sidebar/SubAgentPanel", () => ({
  default: ({ sessionId }: { sessionId?: string }) => (
    <div data-testid="sub-agent-panel" data-session-id={sessionId ?? ""}>
      SubAgentPanel
    </div>
  ),
}));
vi.mock("@/components/sidebar/QuestionsPanel", () => ({
  default: ({ sessionId }: { sessionId?: string }) => (
    <div data-testid="questions-panel" data-session-id={sessionId ?? ""}>
      QuestionsPanel
    </div>
  ),
}));
vi.mock("@/components/sidebar/CheckpointPanel", () => ({
  default: ({ sessionId }: { sessionId?: string }) => (
    <div data-testid="checkpoint-panel" data-session-id={sessionId ?? ""}>
      CheckpointPanel
    </div>
  ),
}));
vi.mock("@/components/sidebar/AgentCommPanel", () => ({
  default: ({ sessionId }: { sessionId?: string }) => (
    <div data-testid="agent-comm-panel" data-session-id={sessionId ?? ""}>
      AgentCommPanel
    </div>
  ),
}));
vi.mock("@/components/SessionHistorySearch", () => ({
  default: ({ sessionId }: { sessionId?: string }) => (
    <div data-testid="search-panel" data-session-id={sessionId ?? ""}>
      SessionHistorySearch
    </div>
  ),
}));
vi.mock("@/components/sidebar/CompactionPanel", () => ({
  default: ({ sessionId }: { sessionId?: string }) => (
    <div data-testid="compaction-panel" data-session-id={sessionId ?? ""}>
      CompactionPanel
    </div>
  ),
}));

describe("SidebarTabs", () => {
  it("renders all tab labels", () => {
    render(<SidebarTabs sessionId="s1" />);

    expect(screen.getByText("ToDo")).toBeInTheDocument();
    expect(screen.getByText("Changed Files")).toBeInTheDocument();
    expect(screen.getByText("Activity")).toBeInTheDocument();
    expect(screen.getByText("Sub-agents")).toBeInTheDocument();
    expect(screen.getByText("Comms")).toBeInTheDocument();
    expect(screen.getByText("Questions")).toBeInTheDocument();
    expect(screen.getByText("Checkpoints")).toBeInTheDocument();
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.getByText("Usage")).toBeInTheDocument();
    expect(screen.getByText("Compaction")).toBeInTheDocument();
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

    await user.click(screen.getByText("Activity"));

    expect(onTabChange).toHaveBeenCalledWith("activity");
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

  it("passes sessionId to SubAgentPanel when sub-agents tab is active", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Sub-agents"));

    const panel = screen.getByTestId("sub-agent-panel");
    expect(panel).toBeInTheDocument();
    expect(panel.getAttribute("data-session-id")).toBe("s1");
  });

  it("the active tab has a distinct CSS class", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    const todoTab = screen.getByText("ToDo");
    expect(todoTab.className).toContain("sidebar-tab-active");

    await user.click(screen.getByText("Activity"));

    expect(todoTab.className).not.toContain("sidebar-tab-active");
    expect(screen.getByText("Activity").className).toContain(
      "sidebar-tab-active",
    );
  });

  it("clicking the Questions tab renders QuestionsPanel", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Questions"));

    expect(screen.getByTestId("questions-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("todo-panel")).not.toBeInTheDocument();
  });

  it("passes sessionId to QuestionsPanel when questions tab is active", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Questions"));

    const panel = screen.getByTestId("questions-panel");
    expect(panel.getAttribute("data-session-id")).toBe("s1");
  });

  it("clicking the Checkpoints tab renders CheckpointPanel", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Checkpoints"));

    expect(screen.getByTestId("checkpoint-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("todo-panel")).not.toBeInTheDocument();
  });

  it("passes sessionId to CheckpointPanel when checkpoints tab is active", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Checkpoints"));

    const panel = screen.getByTestId("checkpoint-panel");
    expect(panel.getAttribute("data-session-id")).toBe("s1");
  });

  it("clicking the Comms tab renders AgentCommPanel with sessionId", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Comms"));

    const panel = screen.getByTestId("agent-comm-panel");
    expect(panel).toBeInTheDocument();
    expect(panel.getAttribute("data-session-id")).toBe("s1");
    expect(screen.queryByTestId("todo-panel")).not.toBeInTheDocument();
  });

  it("clicking the Activity tab renders ActivityPanel", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Activity"));

    expect(screen.getByTestId("activity-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("todo-panel")).not.toBeInTheDocument();
  });

  it("clicking the Search tab renders SessionHistorySearch", async () => {
    const user = userEvent.setup();
    render(<SidebarTabs sessionId="s1" />);

    await user.click(screen.getByText("Search"));

    expect(screen.getByTestId("search-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("todo-panel")).not.toBeInTheDocument();
  });
});
