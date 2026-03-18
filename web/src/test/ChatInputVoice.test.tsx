import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ChatInput from "@/components/ChatInput";

class MockSpeechRecognition {
  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((event: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  start = vi.fn();
  stop = vi.fn(() => {
    this.onend?.();
  });
  abort = vi.fn();
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  dispatchEvent = vi.fn(() => false);

  simulateResult(text: string, isFinal: boolean) {
    this.onresult?.({
      results: {
        length: 1,
        0: {
          isFinal,
          0: { transcript: text },
          length: 1,
        },
        item: (i: number) =>
          i === 0
            ? { isFinal, 0: { transcript: text }, length: 1 }
            : undefined,
        [Symbol.iterator]: function* () {
          yield { isFinal, 0: { transcript: text }, length: 1 };
        },
      },
      resultIndex: 0,
    });
  }
}

let mockInstance: MockSpeechRecognition | null = null;

function createMockMediaStream(): MediaStream {
  const track = {
    stop: vi.fn(),
    kind: "audio",
    id: "mock-track",
    enabled: true,
    readyState: "live",
  } as unknown as MediaStreamTrack;

  return {
    getTracks: vi.fn(() => [track]),
    getAudioTracks: vi.fn(() => [track]),
    getVideoTracks: vi.fn(() => []),
    id: "mock-stream",
    active: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
    addTrack: vi.fn(),
    removeTrack: vi.fn(),
    clone: vi.fn(),
    getTrackById: vi.fn(),
    onaddtrack: null,
    onremovetrack: null,
  } as unknown as MediaStream;
}

describe("ChatInput with voice", () => {
  let originalSpeechRecognition: unknown;

  beforeEach(() => {
    vi.useFakeTimers();

    originalSpeechRecognition = (
      window as unknown as Record<string, unknown>
    ).SpeechRecognition;
    mockInstance = null;

    // Mock getUserMedia so useAudioWaveform works
    if (!navigator.mediaDevices) {
      Object.defineProperty(navigator, "mediaDevices", {
        value: { getUserMedia: vi.fn() },
        writable: true,
        configurable: true,
      });
    }
    navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue(createMockMediaStream());

    // Mock AudioContext
    window.AudioContext = class MockAudioContext {
      createAnalyser = vi.fn(() => ({
        fftSize: 0,
        frequencyBinCount: 128,
        getByteTimeDomainData: vi.fn(),
        connect: vi.fn(),
      }));
      createMediaStreamSource = vi.fn(() => ({
        connect: vi.fn(),
      }));
      close = vi.fn();
      state = "running";
    } as unknown as typeof AudioContext;

    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      return setTimeout(() => cb(performance.now()), 16) as unknown as number;
    });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
      clearTimeout(id);
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();

    if (originalSpeechRecognition) {
      (window as unknown as Record<string, unknown>).SpeechRecognition =
        originalSpeechRecognition;
    } else {
      delete (window as unknown as Record<string, unknown>).SpeechRecognition;
    }
    delete (window as unknown as Record<string, unknown>)
      .webkitSpeechRecognition;
  });

  it("voice button appears in ChatInput when speech recognition is supported", () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      MockSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: "Start voice input" }),
    ).toBeInTheDocument();
  });

  it("voice button is absent from ChatInput when speech recognition is not supported", () => {
    delete (window as unknown as Record<string, unknown>).SpeechRecognition;
    delete (window as unknown as Record<string, unknown>)
      .webkitSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);
    expect(
      screen.queryByRole("button", { name: "Start voice input" }),
    ).not.toBeInTheDocument();
  });

  it("after recording completes, TranscriptPreview is shown with the transcript", async () => {
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);

    // Start listening
    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });

    // Simulate recognition result
    act(() => {
      mockInstance!.simulateResult("test transcript", true);
    });

    // Stop listening via VoiceButton
    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    // Advance past the processing state
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByLabelText("Voice transcript")).toBeInTheDocument();
    expect(screen.getByLabelText("Voice transcript")).toHaveValue(
      "test transcript",
    );
  });

  it("sending from TranscriptPreview triggers the ChatInput onSend callback", async () => {
    const onSend = vi.fn();
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={onSend} />);

    // Start and produce transcript
    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });
    act(() => {
      mockInstance!.simulateResult("voice message", true);
    });
    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    // Advance past processing state
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    // Find the Send button in TranscriptPreview and click it
    const sendButtons = screen.getAllByRole("button", { name: "Send" });
    act(() => {
      sendButtons[0].click();
    });

    expect(onSend).toHaveBeenCalledWith("voice message");
  });

  it("discarding from TranscriptPreview returns to normal input state without sending", async () => {
    const onSend = vi.fn();
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={onSend} />);

    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });
    act(() => {
      mockInstance!.simulateResult("voice message", true);
    });
    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    // Advance past processing state
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    // TranscriptPreview should be visible
    expect(screen.getByLabelText("Voice transcript")).toBeInTheDocument();

    // Click Discard
    act(() => {
      screen.getByRole("button", { name: "Discard" }).click();
    });

    // TranscriptPreview should be gone
    expect(screen.queryByLabelText("Voice transcript")).not.toBeInTheDocument();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows recording overlay with waveform when recording", async () => {
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);

    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });

    expect(screen.getByTestId("recording-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("waveform-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("elapsed-timer")).toBeInTheDocument();
  });

  it("hides recording overlay when not recording", () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      MockSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);

    expect(screen.queryByTestId("recording-overlay")).not.toBeInTheDocument();
  });

  it("shows elapsed timer during recording", async () => {
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);

    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });

    expect(screen.getByTestId("elapsed-timer")).toHaveTextContent("00:00");
  });

  it("shows processing indicator after recording stops", async () => {
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);

    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });

    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    expect(screen.getByTestId("processing-indicator")).toBeInTheDocument();
    expect(screen.getByText("Processing...")).toBeInTheDocument();

    // After timeout, processing indicator disappears
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(
      screen.queryByTestId("processing-indicator"),
    ).not.toBeInTheDocument();
  });

  it("stop button in recording overlay triggers stop", async () => {
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        mockInstance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    render(<ChatInput onSend={vi.fn()} />);

    await act(async () => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });

    expect(screen.getByTestId("recording-overlay")).toBeInTheDocument();

    // Click the stop button in the recording overlay
    act(() => {
      screen.getByRole("button", { name: "Stop recording" }).click();
    });

    // Should now be in processing state
    expect(screen.getByTestId("processing-indicator")).toBeInTheDocument();
  });
});
