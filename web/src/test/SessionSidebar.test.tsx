import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SessionPage from "@/pages/SessionPage";

vi.mock("@/api/client", () => ({
  apiClient: {
    baseURL: "http://localhost:7433",
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

vi.mock("@/context/WebSocketContext", () => ({
  WebSocketProvider: ({
    children,
    sessionId,
  }: {
    children: React.ReactNode;
    sessionId: string;
  }) => (
    <div data-testid="ws-provider" data-session-id={sessionId}>
      {children}
    </div>
  ),
  useWebSocket: () => ({
    connectionState: "disconnected",
    events: [],
    onEvent: vi.fn(),
    removeListener: vi.fn(),
    injectEvents: vi.fn(),
  }),
}));

vi.mock("@/components/ChatPanel", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="chat-panel" data-session-id={sessionId}>
      ChatPanel
    </div>
  ),
}));

vi.mock("@/components/sidebar/SidebarTabs", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="sidebar-tabs" data-session-id={sessionId}>
      SidebarTabs
    </div>
  ),
}));

import { apiClient } from "@/api/client";

const mockGet = vi.mocked(apiClient.get);

const mockSession = {
  id: "sess-123",
  project_id: "proj-1",
  issue_id: null,
  parent_session_id: null,
  name: "Test Session",
  engine: "native",
  mode: "execution",
  status: "executing",
  config: null,
  created_at: "2026-01-01T00:00:00Z",
};

function renderSessionPage(sessionId: string = "sess-123") {
  return render(
    <MemoryRouter initialEntries={[`/sessions/${sessionId}`]}>
      <Routes>
        <Route path="/sessions/:sessionId" element={<SessionPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Collapsible session sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("sidebar renders expanded by default", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-tabs")).toBeInTheDocument();
    });

    const sidebar = screen.getByTestId("session-sidebar");
    expect(sidebar.style.width).toBe("320px");
  });

  it("clicking toggle button collapses the sidebar", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-toggle")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("sidebar-toggle"));

    const sidebar = screen.getByTestId("session-sidebar");
    expect(sidebar.style.width).toBe("32px");
    expect(screen.queryByTestId("sidebar-tabs")).not.toBeInTheDocument();
  });

  it("clicking toggle button again expands the sidebar", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-toggle")).toBeInTheDocument();
    });

    // Collapse
    await user.click(screen.getByTestId("sidebar-toggle"));
    expect(screen.queryByTestId("sidebar-tabs")).not.toBeInTheDocument();

    // Expand
    await user.click(screen.getByTestId("sidebar-toggle"));
    expect(screen.getByTestId("sidebar-tabs")).toBeInTheDocument();

    const sidebar = screen.getByTestId("session-sidebar");
    expect(sidebar.style.width).toBe("320px");
  });

  it("collapsed state is saved to localStorage", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-toggle")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("sidebar-toggle"));
    expect(localStorage.getItem("session-sidebar-collapsed")).toBe("true");

    await user.click(screen.getByTestId("sidebar-toggle"));
    expect(localStorage.getItem("session-sidebar-collapsed")).toBe("false");
  });

  it("respects localStorage collapsed state on mount", async () => {
    localStorage.setItem("session-sidebar-collapsed", "true");

    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("session-sidebar")).toBeInTheDocument();
    });

    const sidebar = screen.getByTestId("session-sidebar");
    expect(sidebar.style.width).toBe("32px");
    expect(screen.queryByTestId("sidebar-tabs")).not.toBeInTheDocument();
  });

  it("toggle button has correct aria-label when expanded", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-toggle")).toBeInTheDocument();
    });

    expect(screen.getByTestId("sidebar-toggle")).toHaveAttribute(
      "aria-label",
      "Collapse sidebar",
    );
  });

  it("toggle button has correct aria-label when collapsed", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-toggle")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("sidebar-toggle"));

    expect(screen.getByTestId("sidebar-toggle")).toHaveAttribute(
      "aria-label",
      "Expand sidebar",
    );
  });
});
