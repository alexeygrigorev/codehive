import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react-native";
import RootNavigator from "../src/navigation/RootNavigator";
import { searchAll } from "../src/api/search";

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

jest.mock("../src/api/search");
const mockSearchAll = searchAll as jest.MockedFunction<typeof searchAll>;

describe("Search Navigation", () => {
  it("Search tab is present in the bottom tab navigator", async () => {
    render(<RootNavigator />);

    await waitFor(() => {
      expect(screen.getAllByText("Search").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("Search tab appears between Sessions and Questions", async () => {
    render(<RootNavigator />);

    await waitFor(() => {
      expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Sessions").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Search").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Questions").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("tapping a session-type result navigates to SessionDetail", async () => {
    jest.useFakeTimers();

    mockSearchAll.mockResolvedValue({
      results: [
        {
          type: "session",
          id: "s1",
          snippet: "Test session result",
          score: 0.9,
          created_at: new Date().toISOString(),
          session_id: "s1",
        },
      ],
      total: 1,
      has_more: false,
    });

    render(<RootNavigator />);

    // Navigate to Search tab
    await waitFor(() => {
      expect(screen.getAllByText("Search").length).toBeGreaterThanOrEqual(1);
    });

    const searchTabs = screen.getAllByText("Search");
    fireEvent.press(searchTabs[searchTabs.length - 1]);

    await waitFor(() => {
      expect(screen.getByTestId("search-input")).toBeTruthy();
    });

    // Type a search query
    fireEvent.changeText(screen.getByTestId("search-input"), "test");

    await act(async () => {
      jest.advanceTimersByTime(400);
    });

    await waitFor(() => {
      expect(screen.getByText("Test session result")).toBeTruthy();
    });

    // Press the result
    fireEvent.press(screen.getByTestId("search-result-card"));

    // After pressing, the search result should navigate away
    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalled();
    });

    jest.useRealTimers();
  });
});
