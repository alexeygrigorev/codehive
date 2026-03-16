import React from "react";
import { render, screen } from "@testing-library/react-native";
import ProjectCard from "../src/components/ProjectCard";

describe("ProjectCard", () => {
  it("renders project name, session count, and status badge", () => {
    render(
      <ProjectCard
        id="p1"
        name="My Project"
        description="A long description that should be truncated"
        sessionCount={3}
        status="idle"
        onPress={jest.fn()}
      />
    );

    expect(screen.getByText("My Project")).toBeTruthy();
    expect(screen.getByText("3 sessions")).toBeTruthy();
    expect(screen.getByTestId("status-badge")).toBeTruthy();
  });
});
