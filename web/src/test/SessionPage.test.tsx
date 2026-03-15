import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SessionPage from "@/pages/SessionPage";

// Mock API client
vi.mock("@/api/client", () => ({
  apiClient: {
    baseURL: "http://localhost:8000",
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
  }),
}));

// Mock ChatPanel to isolate SessionPage tests
vi.mock("@/components/ChatPanel", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="chat-panel" data-session-id={sessionId}>
      ChatPanel
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
  config: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("SessionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});
