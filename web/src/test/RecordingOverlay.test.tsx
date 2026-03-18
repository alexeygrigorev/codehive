import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RecordingOverlay from "@/components/RecordingOverlay";

// Mock ResizeObserver
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

beforeEach(() => {
  window.ResizeObserver =
    MockResizeObserver as unknown as typeof ResizeObserver;
});

describe("RecordingOverlay", () => {
  it("shows waveform and timer when not processing", () => {
    render(
      <RecordingOverlay
        waveformData={new Uint8Array(128)}
        elapsedSeconds={65}
        isProcessing={false}
        onStop={vi.fn()}
      />,
    );

    expect(screen.getByTestId("recording-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("elapsed-timer")).toHaveTextContent("01:05");
    expect(screen.getByTestId("waveform-canvas")).toBeInTheDocument();
  });

  it("shows processing indicator when isProcessing is true", () => {
    render(
      <RecordingOverlay
        waveformData={null}
        elapsedSeconds={0}
        isProcessing={true}
        onStop={vi.fn()}
      />,
    );

    expect(screen.getByTestId("processing-indicator")).toBeInTheDocument();
    expect(screen.getByText("Processing...")).toBeInTheDocument();
    expect(screen.queryByTestId("recording-overlay")).not.toBeInTheDocument();
  });

  it("stop button triggers onStop callback", async () => {
    const onStop = vi.fn();
    const user = userEvent.setup();

    render(
      <RecordingOverlay
        waveformData={new Uint8Array(128)}
        elapsedSeconds={0}
        isProcessing={false}
        onStop={onStop}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Stop recording" }));
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("formats elapsed time correctly in mm:ss", () => {
    const { rerender } = render(
      <RecordingOverlay
        waveformData={null}
        elapsedSeconds={0}
        isProcessing={false}
        onStop={vi.fn()}
      />,
    );
    expect(screen.getByTestId("elapsed-timer")).toHaveTextContent("00:00");

    rerender(
      <RecordingOverlay
        waveformData={null}
        elapsedSeconds={125}
        isProcessing={false}
        onStop={vi.fn()}
      />,
    );
    expect(screen.getByTestId("elapsed-timer")).toHaveTextContent("02:05");
  });
});
