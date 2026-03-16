import React from "react";
import { render, screen, waitFor } from "@testing-library/react-native";
import RootNavigator from "../src/navigation/RootNavigator";

// Mock the API so screens don't make real calls
jest.mock("../src/api/projects", () => ({
  listProjects: jest.fn().mockResolvedValue([]),
}));

jest.mock("../src/api/questions", () => ({
  listQuestions: jest.fn().mockResolvedValue([]),
  answerQuestion: jest.fn(),
}));

jest.mock("../src/api/approvals", () => ({
  listPendingApprovals: jest.fn().mockResolvedValue([]),
  approve: jest.fn(),
  reject: jest.fn(),
}));

describe("RootNavigator", () => {
  it("renders 5 tab buttons with correct labels", async () => {
    render(<RootNavigator />);

    await waitFor(() => {
      expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Sessions").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Questions").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Approvals").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Settings").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows Dashboard screen content by default", async () => {
    render(<RootNavigator />);

    await waitFor(() => {
      const dashboardTexts = screen.getAllByText("Dashboard");
      expect(dashboardTexts.length).toBeGreaterThanOrEqual(1);
    });

    await waitFor(() => {
      expect(screen.getByText("No projects yet")).toBeTruthy();
    });
  });

  it("shows badge counts on Questions and Approvals tabs when non-zero", async () => {
    // Override mocks to return items for badge counts
    const questionsApi = require("../src/api/questions");
    const approvalsApi = require("../src/api/approvals");

    questionsApi.listQuestions.mockResolvedValue([
      {
        id: "q1",
        session_id: "s1",
        question: "Q?",
        answered: false,
        created_at: "2026-03-15T10:00:00Z",
      },
      {
        id: "q2",
        session_id: "s1",
        question: "Q2?",
        answered: false,
        created_at: "2026-03-15T10:00:00Z",
      },
    ]);
    approvalsApi.listPendingApprovals.mockResolvedValue([
      {
        id: "a1",
        session_id: "s1",
        tool_name: "t",
        description: "d",
        status: "pending",
        created_at: "2026-03-15T10:00:00Z",
      },
    ]);

    render(<RootNavigator />);

    // Badge counts are rendered as text by React Navigation
    await waitFor(() => {
      expect(screen.getByText("2")).toBeTruthy();
      expect(screen.getByText("1")).toBeTruthy();
    });
  });
});
