import React from "react";
import { render, screen } from "@testing-library/react-native";
import StatusBadge from "../src/components/StatusBadge";

describe("StatusBadge", () => {
  it('renders green dot and label for "idle" status', () => {
    render(<StatusBadge status="idle" />);
    expect(screen.getByText("idle")).toBeTruthy();
    const dot = screen.getByTestId("status-dot");
    expect(dot.props.style).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ backgroundColor: "#4CAF50" }),
      ])
    );
  });

  it('renders yellow dot and label for "executing" status', () => {
    render(<StatusBadge status="executing" />);
    expect(screen.getByText("executing")).toBeTruthy();
    const dot = screen.getByTestId("status-dot");
    expect(dot.props.style).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ backgroundColor: "#FFC107" }),
      ])
    );
  });

  it('renders red dot and label for "failed" status', () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("failed")).toBeTruthy();
    const dot = screen.getByTestId("status-dot");
    expect(dot.props.style).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ backgroundColor: "#F44336" }),
      ])
    );
  });
});
