import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SessionPage from "@/pages/SessionPage";

// Mock API client
vi.mock("@/api/client", () => ({
  apiClient: {
    baseURL: "http://localhost:7433",
    get: vi.fn(),
    post: vi.fn(),
  },
}));

// Mock WebSocketProvider to avoid actual WebSocket connections
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

// Mock ChatPanel to isolate SessionPage tests
vi.mock("@/components/ChatPanel", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="chat-panel" data-session-id={sessionId}>
      ChatPanel
    </div>
  ),
}));

// Mock SidebarTabs to isolate SessionPage tests
vi.mock("@/components/sidebar/SidebarTabs", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="sidebar-tabs" data-session-id={sessionId}>
      SidebarTabs
    </div>
  ),
}));

import { apiClient } from "@/api/client";

const mockGet = vi.mocked(apiClient.get);

function renderSessionPage(sessionId: string = "sess-123") {
  return render(
    <MemoryRouter initialEntries={[`/sessions/${sessionId}`]}>
      <Routes>
        <Route path="/sessions/:sessionId" element={<SessionPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const mockSession = {
  id: "sess-123",
  project_id: "proj-1",
  issue_id: null,
  parent_session_id: null,
  name: "Test Session",
  engine: "native",
  mode: "execution",
  status: "executing",
  role: null,
  config: null,
  created_at: "2026-01-01T00:00:00Z",
};

const mockProject = {
  id: "proj-1",
  name: "Test Project",
  path: "/path/to/project",
  description: null,
  archetype: null,
  knowledge: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("SessionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders loading state while fetching session metadata", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    renderSessionPage();
    expect(screen.getByText("Loading session...")).toBeInTheDocument();
  });

  it("after fetch, displays session name and status", async () => {
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
    expect(screen.getByText("executing")).toBeInTheDocument();
  });

  it("shows error message if session fetch fails", async () => {
    mockGet.mockResolvedValue(new Response("", { status: 404 }));

    renderSessionPage();

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load session: 404"),
      ).toBeInTheDocument();
    });
  });

  it("passes session ID to WebSocketProvider", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("ws-provider")).toHaveAttribute(
        "data-session-id",
        "sess-123",
      );
    });
  });

  it("renders SidebarTabs alongside ChatPanel", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-tabs")).toHaveAttribute(
        "data-session-id",
        "sess-123",
      );
    });
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
  });

  it("renders ChatPanel with session ID", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("chat-panel")).toHaveAttribute(
        "data-session-id",
        "sess-123",
      );
    });
  });

  it("shows project name as a link when project is loaded", async () => {
    mockGet
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockSession), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockProject), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("project-link")).toBeInTheDocument();
    });
    const link = screen.getByTestId("project-link");
    expect(link).toHaveTextContent("Test Project");
    expect(link).toHaveAttribute("href", "/projects/proj-1");
  });

  it("shows sidebar toggle button", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("sidebar-toggle")).toBeInTheDocument();
    });
  });

  it("shows provider badge when session has provider config", async () => {
    const sessionWithProvider = {
      ...mockSession,
      config: { provider: "zai", model: "glm-4.7" },
    };
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(sessionWithProvider), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("provider-badge")).toBeInTheDocument();
    });
    expect(screen.getByTestId("provider-badge")).toHaveTextContent(
      "Z.ai / glm-4.7",
    );
  });

  it("shows Anthropic provider badge", async () => {
    const sessionWithProvider = {
      ...mockSession,
      config: { provider: "anthropic", model: "claude-sonnet-4-20250514" },
    };
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(sessionWithProvider), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("provider-badge")).toBeInTheDocument();
    });
    expect(screen.getByTestId("provider-badge")).toHaveTextContent(
      "Anthropic / claude-sonnet-4-20250514",
    );
  });

  it("does not show provider badge when config is null", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("provider-badge")).not.toBeInTheDocument();
  });

  it("renders role badge when session has role='swe'", async () => {
    const sessionWithRole = { ...mockSession, role: "swe" };
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(sessionWithRole), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByTestId("role-badge")).toBeInTheDocument();
    });
    expect(screen.getByTestId("role-badge")).toHaveTextContent("SWE");
    expect(screen.getByTestId("role-badge")).toHaveAttribute(
      "title",
      "Software Engineer",
    );
  });

  it("renders no role badge when session has role=null", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("role-badge")).not.toBeInTheDocument();
  });

  it("does not render SessionHistorySearch in main content flow", async () => {
    mockGet.mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    renderSessionPage("sess-123");

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeInTheDocument();
    });
    // SessionHistorySearch should not be rendered directly in the page
    expect(
      screen.queryByTestId("session-history-search"),
    ).not.toBeInTheDocument();
  });
});
