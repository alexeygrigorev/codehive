import React from "react";
import { render, screen, waitFor } from "@testing-library/react-native";
import RootNavigator from "../src/navigation/RootNavigator";

// Mock the API so DashboardScreen doesn't make real calls
jest.mock("../src/api/projects", () => ({
  listProjects: jest.fn().mockResolvedValue([]),
}));

describe("RootNavigator", () => {
  it("renders 4 tab buttons with correct labels", async () => {
    render(<RootNavigator />);

    await waitFor(() => {
      expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Sessions").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Questions").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Settings").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows Dashboard screen content by default", async () => {
    render(<RootNavigator />);

    // Dashboard is the first tab and should be active
    // With the nested stack, "Dashboard" appears in the stack header and the tab bar label
    await waitFor(() => {
      const dashboardTexts = screen.getAllByText("Dashboard");
      expect(dashboardTexts.length).toBeGreaterThanOrEqual(1);
    });

    // The dashboard screen itself should show "No projects yet" since the mock returns []
    await waitFor(() => {
      expect(screen.getByText("No projects yet")).toBeTruthy();
    });
  });
});
