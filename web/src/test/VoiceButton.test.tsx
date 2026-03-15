import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import VoiceButton from "@/components/VoiceButton";

describe("VoiceButton", () => {
  it('renders a button with aria-label "Start voice input" when idle', () => {
    render(
      <VoiceButton
        isListening={false}
        isSupported={true}
        onStartListening={vi.fn()}
        onStopListening={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Start voice input" }),
    ).toBeInTheDocument();
  });

  it('renders a button with aria-label "Stop voice input" when recording', () => {
    render(
      <VoiceButton
        isListening={true}
        isSupported={true}
        onStartListening={vi.fn()}
        onStopListening={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Stop voice input" }),
    ).toBeInTheDocument();
  });

  it("calls onStartListening when clicked in idle state", async () => {
    const onStart = vi.fn();
    const user = userEvent.setup();
    render(
      <VoiceButton
        isListening={false}
        isSupported={true}
        onStartListening={onStart}
        onStopListening={vi.fn()}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Start voice input" }),
    );
    expect(onStart).toHaveBeenCalledOnce();
  });

  it("calls onStopListening when clicked in recording state", async () => {
    const onStop = vi.fn();
    const user = userEvent.setup();
    render(
      <VoiceButton
        isListening={true}
        isSupported={true}
        onStartListening={vi.fn()}
        onStopListening={onStop}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Stop voice input" }),
    );
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("returns null when isSupported is false", () => {
    const { container } = render(
      <VoiceButton
        isListening={false}
        isSupported={false}
        onStartListening={vi.fn()}
        onStopListening={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("applies a visual recording indicator class when isListening is true", () => {
    render(
      <VoiceButton
        isListening={true}
        isSupported={true}
        onStartListening={vi.fn()}
        onStopListening={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "Stop voice input" });
    expect(button.className).toContain("voice-recording");
  });
});
