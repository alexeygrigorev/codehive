import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChatPanel from "@/components/ChatPanel";
import type { SessionEvent } from "@/api/websocket";

vi.mock("@/hooks/useSessionEvents", () => ({
  useSessionEvents: vi.fn(),
}));

vi.mock("@/api/messages", () => ({
  sendMessage: vi.fn(),
}));

vi.mock("@/api/approvals", () => ({
  approveAction: vi.fn(),
  rejectAction: vi.fn(),
}));

import { useSessionEvents } from "@/hooks/useSessionEvents";
import { approveAction, rejectAction } from "@/api/approvals";

const mockUseSessionEvents = vi.mocked(useSessionEvents);
const mockApproveAction = vi.mocked(approveAction);
const mockRejectAction = vi.mocked(rejectAction);

function makeEvent(
  id: string,
  type: string,
  data: Record<string, unknown>,
): SessionEvent {
  return {
    id,
    session_id: "s1",
    type,
    data,
    created_at: new Date().toISOString(),
  };
}

describe("ChatPanel with approval events", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders ApprovalPrompt when an approval.required event arrives", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "approval.required", {
        action_id: "act-1",
        description: "Run dangerous command",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("Run dangerous command")).toBeInTheDocument();
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
  });

  it("renders approval prompt in chronological order among messages", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Do something",
      }),
      makeEvent("e2", "approval.required", {
        action_id: "act-1",
        description: "Confirm action",
      }),
      makeEvent("e3", "message.created", {
        role: "assistant",
        content: "Action completed",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);

    const doSomething = screen.getByText("Do something");
    const confirmAction = screen.getByText("Confirm action");
    const actionCompleted = screen.getByText("Action completed");

    // Verify DOM order
    expect(
      doSomething.compareDocumentPosition(confirmAction) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      confirmAction.compareDocumentPosition(actionCompleted) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("approving via the prompt calls the API and updates to resolved state", async () => {
    mockApproveAction.mockResolvedValue(undefined);
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "approval.required", {
        action_id: "act-1",
        description: "Run command",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);

    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() => {
      expect(mockApproveAction).toHaveBeenCalledWith("s1", "act-1");
    });

    await waitFor(() => {
      expect(screen.getByText("Approved")).toBeInTheDocument();
    });
  });

  it("rejecting via the prompt calls the API and updates to rejected state", async () => {
    mockRejectAction.mockResolvedValue(undefined);
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "approval.required", {
        action_id: "act-1",
        description: "Run command",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);

    fireEvent.click(screen.getByText("Reject"));

    await waitFor(() => {
      expect(mockRejectAction).toHaveBeenCalledWith("s1", "act-1");
    });

    await waitFor(() => {
      expect(screen.getByText("Rejected")).toBeInTheDocument();
    });
  });

  it("uses tool_name as fallback description when description is not present", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "approval.required", {
        action_id: "act-1",
        tool_name: "execute_shell",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("execute_shell")).toBeInTheDocument();
  });
});
