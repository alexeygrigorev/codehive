import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useVoiceInput } from "@/hooks/useVoiceInput";

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

describe("useVoiceInput", () => {
  let originalSpeechRecognition: unknown;

  beforeEach(() => {
    originalSpeechRecognition = (
      window as unknown as Record<string, unknown>
    ).SpeechRecognition;
  });

  afterEach(() => {
    if (originalSpeechRecognition) {
      (window as unknown as Record<string, unknown>).SpeechRecognition =
        originalSpeechRecognition;
    } else {
      delete (window as unknown as Record<string, unknown>).SpeechRecognition;
    }
  });

  it("returns isSupported: false when SpeechRecognition is not available", () => {
    delete (window as unknown as Record<string, unknown>).SpeechRecognition;
    delete (window as unknown as Record<string, unknown>)
      .webkitSpeechRecognition;

    const { result } = renderHook(() => useVoiceInput());
    expect(result.current.isSupported).toBe(false);
  });

  it("returns isSupported: true when SpeechRecognition is available", () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() => useVoiceInput());
    expect(result.current.isSupported).toBe(true);
  });

  it("startListening sets isListening to true", () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() => useVoiceInput());

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);
  });

  it("stopListening sets isListening to false", () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      MockSpeechRecognition;

    const { result } = renderHook(() => useVoiceInput());

    act(() => {
      result.current.startListening();
    });
    expect(result.current.isListening).toBe(true);

    act(() => {
      result.current.stopListening();
    });
    expect(result.current.isListening).toBe(false);
  });

  it("populates transcript with recognized text from result event", () => {
    let instance: MockSpeechRecognition | null = null;
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        instance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    const { result } = renderHook(() => useVoiceInput());

    act(() => {
      result.current.startListening();
    });

    act(() => {
      instance!.simulateResult("hello world", true);
    });

    expect(result.current.transcript).toBe("hello world");
  });

  it("resetTranscript clears transcript back to empty string", () => {
    let instance: MockSpeechRecognition | null = null;
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        instance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    const { result } = renderHook(() => useVoiceInput());

    act(() => {
      result.current.startListening();
    });

    act(() => {
      instance!.simulateResult("hello", true);
    });
    expect(result.current.transcript).toBe("hello");

    act(() => {
      result.current.resetTranscript();
    });
    expect(result.current.transcript).toBe("");
  });

  it("cleans up by calling abort on unmount", () => {
    let instance: MockSpeechRecognition | null = null;
    const CapturingSpeechRecognition = class extends MockSpeechRecognition {
      constructor() {
        super();
        instance = this;
      }
    };
    (window as unknown as Record<string, unknown>).SpeechRecognition =
      CapturingSpeechRecognition;

    const { result, unmount } = renderHook(() => useVoiceInput());

    act(() => {
      result.current.startListening();
    });

    unmount();

    expect(instance!.abort).toHaveBeenCalled();
  });
});
