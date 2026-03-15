import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("ChatInput with voice", () => {
  let originalSpeechRecognition: unknown;

  beforeEach(() => {
    originalSpeechRecognition = (
      window as unknown as Record<string, unknown>
    ).SpeechRecognition;
    mockInstance = null;
  });

  afterEach(() => {
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

  it("after recording completes, TranscriptPreview is shown with the transcript", () => {
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
    act(() => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });

    // Simulate recognition result
    act(() => {
      mockInstance!.simulateResult("test transcript", true);
    });

    // Stop listening
    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    expect(screen.getByLabelText("Voice transcript")).toBeInTheDocument();
    expect(screen.getByLabelText("Voice transcript")).toHaveValue(
      "test transcript",
    );
  });

  it("sending from TranscriptPreview triggers the ChatInput onSend callback", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
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
    act(() => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });
    act(() => {
      mockInstance!.simulateResult("voice message", true);
    });
    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    // Find the Send button in TranscriptPreview (there are two Send buttons)
    const sendButtons = screen.getAllByRole("button", { name: "Send" });
    // The TranscriptPreview Send button is the one inside the preview
    await user.click(sendButtons[0]);

    expect(onSend).toHaveBeenCalledWith("voice message");
  });

  it("discarding from TranscriptPreview returns to normal input state without sending", () => {
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

    act(() => {
      screen.getByRole("button", { name: "Start voice input" }).click();
    });
    act(() => {
      mockInstance!.simulateResult("voice message", true);
    });
    act(() => {
      screen.getByRole("button", { name: "Stop voice input" }).click();
    });

    // TranscriptPreview should be visible
    expect(screen.getByLabelText("Voice transcript")).toBeInTheDocument();

    // Click Discard
    act(() => {
      screen.getByRole("button", { name: "Discard" }).click();
    });

    // TranscriptPreview should be gone
    expect(screen.queryByLabelText("Voice transcript")).not.toBeInTheDocument();
    // onSend should not have been called
    expect(onSend).not.toHaveBeenCalled();
  });
});
