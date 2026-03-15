import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import ReplayTimeline from "@/components/ReplayTimeline";
import type { ReplayStep } from "@/api/replay";

const mockSteps: ReplayStep[] = [
  {
    index: 0,
    timestamp: "2026-01-01T12:00:00Z",
    step_type: "message",
    data: {},
  },
  {
    index: 1,
    timestamp: "2026-01-01T12:00:01Z",
    step_type: "tool_call_start",
    data: {},
  },
  {
    index: 2,
    timestamp: "2026-01-01T12:00:02Z",
    step_type: "file_change",
    data: {},
  },
];

describe("ReplayTimeline", () => {
  it("renders one marker per step", () => {
    const onStepClick = vi.fn();
    render(
      <ReplayTimeline
        steps={mockSteps}
        currentIndex={0}
        onStepClick={onStepClick}
      />,
    );

    const markers = screen.getAllByRole("button");
    expect(markers).toHaveLength(3);
  });

  it("highlights the current step", () => {
    const onStepClick = vi.fn();
    render(
      <ReplayTimeline
        steps={mockSteps}
        currentIndex={1}
        onStepClick={onStepClick}
      />,
    );

    const markers = screen.getAllByRole("button");
    // The current step (index 1) should have the blue bg class
    expect(markers[1].className).toContain("bg-blue-600");
    // Other steps should not
    expect(markers[0].className).not.toContain("bg-blue-600");
    expect(markers[2].className).not.toContain("bg-blue-600");
  });

  it("clicking a marker calls onStepClick with the step index", async () => {
    const onStepClick = vi.fn();
    render(
      <ReplayTimeline
        steps={mockSteps}
        currentIndex={0}
        onStepClick={onStepClick}
      />,
    );

    const markers = screen.getAllByRole("button");
    await userEvent.click(markers[2]);

    expect(onStepClick).toHaveBeenCalledWith(2);
  });

  it("displays correct labels for step types", () => {
    const onStepClick = vi.fn();
    render(
      <ReplayTimeline
        steps={mockSteps}
        currentIndex={0}
        onStepClick={onStepClick}
      />,
    );

    expect(screen.getByText("MSG")).toBeInTheDocument();
    expect(screen.getByText("TOOL")).toBeInTheDocument();
    expect(screen.getByText("FILE")).toBeInTheDocument();
  });
});
