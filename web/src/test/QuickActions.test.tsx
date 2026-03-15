import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import QuickActions from "@/components/mobile/QuickActions";
import type { PendingApproval } from "@/components/mobile/QuickActions";

describe("QuickActions", () => {
  it("renders Approve and Reject buttons when there are pending approvals", () => {
    const approvals: PendingApproval[] = [
      { actionId: "a1", description: "Run deploy script" },
    ];

    render(
      <QuickActions
        pendingApprovals={approvals}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByText("Run deploy script")).toBeInTheDocument();
  });

  it("calls onApprove with the correct action ID when Approve is clicked", async () => {
    const onApprove = vi.fn();
    const approvals: PendingApproval[] = [
      { actionId: "action-42", description: "Execute migration" },
    ];

    render(
      <QuickActions
        pendingApprovals={approvals}
        onApprove={onApprove}
        onReject={vi.fn()}
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /approve/i }));

    expect(onApprove).toHaveBeenCalledWith("action-42");
  });

  it("returns null when there are no pending approvals", () => {
    const { container } = render(
      <QuickActions
        pendingApprovals={[]}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(container.innerHTML).toBe("");
  });

  it("calls onReject with the correct action ID when Reject is clicked", async () => {
    const onReject = vi.fn();
    const approvals: PendingApproval[] = [
      { actionId: "action-99", description: "Delete resources" },
    ];

    render(
      <QuickActions
        pendingApprovals={approvals}
        onApprove={vi.fn()}
        onReject={onReject}
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /reject/i }));

    expect(onReject).toHaveBeenCalledWith("action-99");
  });
});
