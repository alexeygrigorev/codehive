import React from "react";
import { render, screen } from "@testing-library/react-native";
import RootNavigator from "../src/navigation/RootNavigator";

describe("RootNavigator", () => {
  it("renders 4 tab buttons with correct labels", () => {
    render(<RootNavigator />);

    // Each tab label appears multiple times (header, tab bar, screen content)
    // so we use getAllByText and check they exist
    expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Sessions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Questions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Settings").length).toBeGreaterThanOrEqual(1);
  });

  it("shows Dashboard screen content by default", () => {
    render(<RootNavigator />);
    // Dashboard is the first tab and should be active
    const dashboardTexts = screen.getAllByText("Dashboard");
    // There should be at least 2: tab bar label + screen content (+ header)
    expect(dashboardTexts.length).toBeGreaterThanOrEqual(2);
  });
});
