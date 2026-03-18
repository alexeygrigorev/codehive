import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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
  useWebSocketSafe: () => null,
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
const mockPatch = vi.mocked(apiClient.patch);

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

describe("SessionPage with mode and approvals", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("shows SessionModeIndicator with the session's current mode", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByText("execution")).toBeInTheDocument();
    });
    // The mode indicator should be in the header
    const modeIndicator = screen
      .getByText("execution")
      .closest(".mode-indicator");
    expect(modeIndicator).toBeInTheDocument();
  });

  it("shows ApprovalBadge in the header (hidden when no approvals)", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { container } = renderSessionPage();

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });
    // Badge should be hidden (count is 0)
    expect(
      container.querySelector(".approval-badge"),
    ).not.toBeInTheDocument();
  });

  it("toggles SessionModeSwitcher when mode indicator is clicked", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });

    // Switcher should not be visible yet
    expect(screen.queryByText("brainstorm")).not.toBeInTheDocument();

    // Click mode indicator button to show switcher
    fireEvent.click(screen.getByLabelText("Toggle mode switcher"));

    // All 5 modes should now be visible
    expect(screen.getByText("brainstorm")).toBeInTheDocument();
    expect(screen.getByText("interview")).toBeInTheDocument();
    expect(screen.getByText("planning")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("switching mode via SessionModeSwitcher updates the indicator after API success", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    mockPatch.mockResolvedValue(new Response("", { status: 200 }));

    renderSessionPage();

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });

    // Open the switcher
    fireEvent.click(screen.getByLabelText("Toggle mode switcher"));

    // Click "review" mode
    fireEvent.click(screen.getByText("review"));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/sessions/sess-123", {
        mode: "review",
      });
    });

    // Mode indicator should update to "review"
    await waitFor(() => {
      const indicator = screen
        .getAllByText("review")
        .find((el) => el.closest(".mode-indicator"));
      expect(indicator).toBeInTheDocument();
    });
  });
});
