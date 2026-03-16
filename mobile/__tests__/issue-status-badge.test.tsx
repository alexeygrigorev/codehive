import React from "react";
import { render, screen } from "@testing-library/react-native";
import IssueStatusBadge from "../src/components/IssueStatusBadge";

describe("IssueStatusBadge", () => {
  it('renders blue dot and label for "open" status', () => {
    render(<IssueStatusBadge status="open" />);
    expect(screen.getByText("open")).toBeTruthy();
    const dot = screen.getByTestId("issue-status-dot");
    expect(dot.props.style).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ backgroundColor: "#2196F3" }),
      ])
    );
  });

  it('renders yellow dot and label for "in_progress" status', () => {
    render(<IssueStatusBadge status="in_progress" />);
    expect(screen.getByText("in_progress")).toBeTruthy();
    const dot = screen.getByTestId("issue-status-dot");
    expect(dot.props.style).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ backgroundColor: "#FFC107" }),
      ])
    );
  });

  it('renders green dot and label for "closed" status', () => {
    render(<IssueStatusBadge status="closed" />);
    expect(screen.getByText("closed")).toBeTruthy();
    const dot = screen.getByTestId("issue-status-dot");
    expect(dot.props.style).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ backgroundColor: "#4CAF50" }),
      ])
    );
  });
});
