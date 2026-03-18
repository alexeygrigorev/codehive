import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AudioWaveform from "@/components/AudioWaveform";

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

describe("AudioWaveform", () => {
  it("renders a canvas element", () => {
    render(<AudioWaveform waveformData={null} />);
    const canvas = screen.getByTestId("waveform-canvas");
    expect(canvas).toBeInTheDocument();
    expect(canvas.tagName).toBe("CANVAS");
  });

  it("renders with null waveformData without crashing", () => {
    const { container } = render(<AudioWaveform waveformData={null} />);
    expect(container.querySelector("canvas")).toBeInTheDocument();
  });

  it("renders with all-zero waveformData (silence)", () => {
    const data = new Uint8Array(128).fill(128);
    const { container } = render(<AudioWaveform waveformData={data} />);
    expect(container.querySelector("canvas")).toBeInTheDocument();
  });

  it("accepts waveformData prop and renders without error", () => {
    const data = new Uint8Array(128);
    for (let i = 0; i < 128; i++) {
      data[i] = Math.floor(Math.random() * 256);
    }
    render(<AudioWaveform waveformData={data} />);
    expect(screen.getByTestId("waveform-canvas")).toBeInTheDocument();
  });

  it("applies custom height", () => {
    render(<AudioWaveform waveformData={null} height={64} />);
    const canvas = screen.getByTestId("waveform-canvas");
    expect(canvas).toHaveAttribute("height", "64");
  });
});
