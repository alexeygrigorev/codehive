import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import SessionModeSwitcher from "@/components/SessionModeSwitcher";
import { SESSION_MODES } from "@/components/SessionModeIndicator";

describe("SessionModeSwitcher", () => {
  it("renders buttons for all 5 modes", () => {
    render(
      <SessionModeSwitcher currentMode="execution" onModeChange={vi.fn()} />,
    );
    for (const mode of SESSION_MODES) {
      expect(screen.getByText(mode)).toBeInTheDocument();
    }
  });

  it("highlights the currently active mode with aria-pressed", () => {
    render(
      <SessionModeSwitcher currentMode="planning" onModeChange={vi.fn()} />,
    );
    const planningBtn = screen.getByText("planning");
    expect(planningBtn).toHaveAttribute("aria-pressed", "true");
    const otherBtn = screen.getByText("execution");
    expect(otherBtn).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onModeChange with the selected mode when clicking a non-active mode", () => {
    const onModeChange = vi.fn();
    render(
      <SessionModeSwitcher
        currentMode="execution"
        onModeChange={onModeChange}
      />,
    );
    fireEvent.click(screen.getByText("review"));
    expect(onModeChange).toHaveBeenCalledWith("review");
  });

  it("does not call onModeChange when clicking the already-active mode", () => {
    const onModeChange = vi.fn();
    render(
      <SessionModeSwitcher
        currentMode="execution"
        onModeChange={onModeChange}
      />,
    );
    fireEvent.click(screen.getByText("execution"));
    expect(onModeChange).not.toHaveBeenCalled();
  });

  it("disables all buttons when disabled prop is true", () => {
    render(
      <SessionModeSwitcher
        currentMode="execution"
        onModeChange={vi.fn()}
        disabled={true}
      />,
    );
    for (const mode of SESSION_MODES) {
      expect(screen.getByText(mode)).toBeDisabled();
    }
  });

  it("shows loading state while mode change is in progress", () => {
    render(
      <SessionModeSwitcher
        currentMode="execution"
        onModeChange={vi.fn()}
        loading={true}
      />,
    );
    expect(screen.getByText("Saving...")).toBeInTheDocument();
    for (const mode of SESSION_MODES) {
      expect(screen.getByText(mode)).toBeDisabled();
    }
  });
});
