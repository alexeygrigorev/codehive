import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ApprovalPrompt from "@/components/ApprovalPrompt";

describe("ApprovalPrompt", () => {
  const defaultProps = {
    actionId: "act-1",
    description: "Execute shell command: rm -rf /tmp/test",
    onApprove: vi.fn(),
    onReject: vi.fn(),
  };

  it("renders the action description", () => {
    render(<ApprovalPrompt {...defaultProps} />);
    expect(
      screen.getByText("Execute shell command: rm -rf /tmp/test"),
    ).toBeInTheDocument();
  });

  it("renders Approve and Reject buttons in pending state", () => {
    render(<ApprovalPrompt {...defaultProps} />);
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
  });

  it("calls onApprove with actionId when Approve is clicked", () => {
    const onApprove = vi.fn();
    render(<ApprovalPrompt {...defaultProps} onApprove={onApprove} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onApprove).toHaveBeenCalledWith("act-1");
  });

  it("calls onReject with actionId when Reject is clicked", () => {
    const onReject = vi.fn();
    render(<ApprovalPrompt {...defaultProps} onReject={onReject} />);
    fireEvent.click(screen.getByText("Reject"));
    expect(onReject).toHaveBeenCalledWith("act-1");
  });

  it("disables both buttons when loading is true", () => {
    render(<ApprovalPrompt {...defaultProps} loading={true} />);
    expect(screen.getByText("Approve")).toBeDisabled();
    expect(screen.getByText("Reject")).toBeDisabled();
  });

  it("shows 'Approved' resolved state after approval", () => {
    render(<ApprovalPrompt {...defaultProps} status="approved" />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.queryByText("Approve")).not.toBeInTheDocument();
    expect(screen.queryByText("Reject")).not.toBeInTheDocument();
  });

  it("shows 'Rejected' resolved state after rejection", () => {
    render(<ApprovalPrompt {...defaultProps} status="rejected" />);
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.queryByText("Approve")).not.toBeInTheDocument();
    expect(screen.queryByText("Reject")).not.toBeInTheDocument();
  });
});
