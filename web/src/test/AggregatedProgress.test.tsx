import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AggregatedProgress from "@/components/AggregatedProgress";

describe("AggregatedProgress", () => {
  it("displays correct completed/total text and progress bar width", () => {
    render(<AggregatedProgress total={3} completed={2} />);

    expect(screen.getByText("2/3 completed")).toBeInTheDocument();

    const bar = document.querySelector(".progress-bar") as HTMLElement;
    expect(bar).not.toBeNull();
    expect(bar.style.width).toBe("67%");
  });

  it("handles zero sub-agents gracefully", () => {
    render(<AggregatedProgress total={0} completed={0} />);

    expect(screen.getByText("0/0 completed")).toBeInTheDocument();

    const bar = document.querySelector(".progress-bar") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });

  it("shows 100% when all sub-agents are completed", () => {
    render(<AggregatedProgress total={5} completed={5} />);

    expect(screen.getByText("5/5 completed")).toBeInTheDocument();

    const bar = document.querySelector(".progress-bar") as HTMLElement;
    expect(bar.style.width).toBe("100%");
  });
});
