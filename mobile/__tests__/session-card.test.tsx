import React from "react";
import { render, screen } from "@testing-library/react-native";
import SessionCard from "../src/components/SessionCard";

describe("SessionCard", () => {
  it("renders session name, mode, and status badge", () => {
    render(
      <SessionCard
        id="s1"
        name="Fix tests"
        mode="execution"
        status="executing"
        updatedAt={new Date().toISOString()}
        onPress={jest.fn()}
      />
    );

    expect(screen.getByText("Fix tests")).toBeTruthy();
    expect(screen.getByText("execution")).toBeTruthy();
    expect(screen.getByTestId("status-badge")).toBeTruthy();
  });
});
