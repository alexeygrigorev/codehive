import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import ApprovalCard, {
  type Approval,
} from "../src/components/ApprovalCard";

const pendingApproval: Approval = {
  id: "a1",
  session_id: "s1",
  tool_name: "file_write",
  description: "Write to config.yaml",
  status: "pending",
  created_at: "2026-03-15T10:00:00Z",
};

describe("ApprovalCard", () => {
  it("renders pending approval with description, tool name, and buttons", () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    render(
      <ApprovalCard
        approval={pendingApproval}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByText("Write to config.yaml")).toBeTruthy();
    expect(screen.getByText("Tool: file_write")).toBeTruthy();
    expect(screen.getByText("Approve")).toBeTruthy();
    expect(screen.getByText("Reject")).toBeTruthy();
  });

  it("calls onApprove with correct id when Approve is pressed", () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    render(
      <ApprovalCard
        approval={pendingApproval}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    fireEvent.press(screen.getByTestId("approve-button"));

    expect(onApprove).toHaveBeenCalledWith("a1");
    expect(onReject).not.toHaveBeenCalled();
  });

  it("calls onReject with correct id when Reject is pressed", () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    render(
      <ApprovalCard
        approval={pendingApproval}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    fireEvent.press(screen.getByTestId("reject-button"));

    expect(onReject).toHaveBeenCalledWith("a1");
    expect(onApprove).not.toHaveBeenCalled();
  });
});
