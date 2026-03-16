import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import IssueCard from "../src/components/IssueCard";

describe("IssueCard", () => {
  it("renders issue title, status badge, and timestamp", () => {
    render(
      <IssueCard
        id="i1"
        title="Fix login bug"
        status="open"
        createdAt="2026-03-15T10:00:00Z"
        onPress={jest.fn()}
      />
    );

    expect(screen.getByText("Fix login bug")).toBeTruthy();
    expect(screen.getByTestId("issue-status-badge")).toBeTruthy();
    // Timestamp should be rendered (relative time)
    expect(screen.getByText(/ago|unknown/)).toBeTruthy();
  });

  it("calls onPress when pressed", () => {
    const onPress = jest.fn();
    render(
      <IssueCard
        id="i1"
        title="Fix login bug"
        status="open"
        createdAt="2026-03-15T10:00:00Z"
        onPress={onPress}
      />
    );

    fireEvent.press(screen.getByTestId("issue-card"));
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
