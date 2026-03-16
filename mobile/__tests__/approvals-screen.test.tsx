import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from "@testing-library/react-native";
import ApprovalsScreen from "../src/screens/ApprovalsScreen";
import {
  listPendingApprovals,
  approve,
  reject,
} from "../src/api/approvals";

jest.mock("../src/api/approvals");
const mockListPendingApprovals = listPendingApprovals as jest.MockedFunction<
  typeof listPendingApprovals
>;
const mockApprove = approve as jest.MockedFunction<typeof approve>;
const mockReject = reject as jest.MockedFunction<typeof reject>;

const ASYNC_TIMEOUT = 15000;

describe("ApprovalsScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it(
    "renders pending approvals from the API",
    async () => {
      mockListPendingApprovals.mockResolvedValue([
        {
          id: "a1",
          session_id: "s1",
          tool_name: "file_write",
          description: "Write config.yaml",
          status: "pending",
          created_at: "2026-03-15T10:00:00Z",
        },
        {
          id: "a2",
          session_id: "s2",
          tool_name: "shell_exec",
          description: "Run migrations",
          status: "pending",
          created_at: "2026-03-15T11:00:00Z",
        },
      ]);

      render(<ApprovalsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("Write config.yaml")).toBeTruthy();
          expect(screen.getByText("Run migrations")).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "shows empty state when no pending approvals",
    async () => {
      mockListPendingApprovals.mockResolvedValue([]);

      render(<ApprovalsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("No pending approvals")).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "calls approve and removes the card",
    async () => {
      mockListPendingApprovals.mockResolvedValue([
        {
          id: "a1",
          session_id: "s1",
          tool_name: "file_write",
          description: "Write config.yaml",
          status: "pending",
          created_at: "2026-03-15T10:00:00Z",
        },
      ]);
      mockApprove.mockResolvedValue({});

      render(<ApprovalsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("Write config.yaml")).toBeTruthy();
        },
        { timeout: 5000 },
      );

      fireEvent.press(screen.getByTestId("approve-button"));

      await waitFor(() => {
        expect(mockApprove).toHaveBeenCalledWith("a1");
      });

      await waitFor(() => {
        expect(screen.queryByText("Write config.yaml")).toBeNull();
      });
    },
    ASYNC_TIMEOUT,
  );

  it(
    "calls reject and removes the card",
    async () => {
      mockListPendingApprovals.mockResolvedValue([
        {
          id: "a1",
          session_id: "s1",
          tool_name: "file_write",
          description: "Write config.yaml",
          status: "pending",
          created_at: "2026-03-15T10:00:00Z",
        },
      ]);
      mockReject.mockResolvedValue({});

      render(<ApprovalsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("Write config.yaml")).toBeTruthy();
        },
        { timeout: 5000 },
      );

      fireEvent.press(screen.getByTestId("reject-button"));

      await waitFor(() => {
        expect(mockReject).toHaveBeenCalledWith("a1");
      });

      await waitFor(() => {
        expect(screen.queryByText("Write config.yaml")).toBeNull();
      });
    },
    ASYNC_TIMEOUT,
  );
});
