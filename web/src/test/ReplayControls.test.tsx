import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ReplayControls from "@/components/ReplayControls";

describe("ReplayControls", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("disables Previous on first step", () => {
    render(
      <ReplayControls
        currentIndex={0}
        totalSteps={5}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("disables Next on last step", () => {
    render(
      <ReplayControls
        currentIndex={4}
        totalSteps={5}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows step indicator", () => {
    render(
      <ReplayControls
        currentIndex={2}
        totalSteps={5}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    expect(screen.getByText("Step 3 of 5")).toBeInTheDocument();
  });

  it("calls onPrevious and onNext when buttons are clicked", async () => {
    const onPrevious = vi.fn();
    const onNext = vi.fn();

    render(
      <ReplayControls
        currentIndex={2}
        totalSteps={5}
        onPrevious={onPrevious}
        onNext={onNext}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(onPrevious).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it("Play button starts auto-advance; Pause stops it", async () => {
    const onNext = vi.fn();

    render(
      <ReplayControls
        currentIndex={0}
        totalSteps={5}
        onPrevious={vi.fn()}
        onNext={onNext}
        autoAdvanceInterval={1000}
      />,
    );

    // Click Play
    await userEvent.click(screen.getByRole("button", { name: "Play" }));

    // After 1 tick of the interval, onNext should be called
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onNext).toHaveBeenCalledTimes(1);

    // Click Pause
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));

    // After another tick, onNext should NOT be called again
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it("auto-advance stops at last step", async () => {
    const onNext = vi.fn();

    // Render at the last step
    render(
      <ReplayControls
        currentIndex={4}
        totalSteps={5}
        onPrevious={vi.fn()}
        onNext={onNext}
        autoAdvanceInterval={1000}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Play" }));

    // After a tick, onNext should NOT be called since we're at the last step
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onNext).not.toHaveBeenCalled();

    // Button should have switched back to "Play" since it auto-stopped
    expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
  });
});
