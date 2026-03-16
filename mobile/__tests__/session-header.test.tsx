import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import SessionHeader from "../src/components/SessionHeader";

describe("SessionHeader", () => {
  it("renders session name, mode, and status badge", () => {
    render(
      <SessionHeader
        name="Fix authentication"
        mode="execution"
        status="executing"
        onBack={jest.fn()}
      />
    );

    expect(screen.getByText("Fix authentication")).toBeTruthy();
    expect(screen.getByText("execution")).toBeTruthy();
    expect(screen.getByTestId("status-badge")).toBeTruthy();
  });

  it("renders StatusBadge with executing state", () => {
    render(
      <SessionHeader
        name="Deploy service"
        mode="review"
        status="executing"
        onBack={jest.fn()}
      />
    );

    expect(screen.getByText("executing")).toBeTruthy();
    expect(screen.getByTestId("status-badge")).toBeTruthy();
  });

  it("calls onBack when back button is pressed", () => {
    const onBack = jest.fn();
    render(
      <SessionHeader
        name="Test"
        mode="brainstorm"
        status="idle"
        onBack={onBack}
      />
    );

    fireEvent.press(screen.getByTestId("back-button"));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
