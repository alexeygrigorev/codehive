import { renderHook, act } from "@testing-library/react-native";
import { useVoiceRecognition } from "../src/hooks/useVoiceRecognition";
import Voice from "@react-native-voice/voice";
import {
  _simulateSpeechResults,
  _simulateSpeechError,
} from "../__mocks__/@react-native-voice/voice";

jest.mock("@react-native-voice/voice");

const mockVoice = Voice as jest.Mocked<typeof Voice>;

describe("useVoiceRecognition", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockVoice.isAvailable.mockResolvedValue(1);
    mockVoice.start.mockResolvedValue(undefined);
    mockVoice.stop.mockResolvedValue(undefined);
  });

  it("initializes with default state", async () => {
    const { result } = renderHook(() => useVoiceRecognition());

    expect(result.current.isListening).toBe(false);
    expect(result.current.transcript).toBe("");
    expect(result.current.error).toBeNull();
  });

  it("calling startListening sets isListening true and calls Voice.start", async () => {
    const { result } = renderHook(() => useVoiceRecognition());

    await act(async () => {
      await result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);
    expect(mockVoice.start).toHaveBeenCalledWith("en-US");
  });

  it("calling stopListening sets isListening false and calls Voice.stop", async () => {
    const { result } = renderHook(() => useVoiceRecognition());

    await act(async () => {
      await result.current.startListening();
    });
    expect(result.current.isListening).toBe(true);

    await act(async () => {
      await result.current.stopListening();
    });

    expect(result.current.isListening).toBe(false);
    expect(mockVoice.stop).toHaveBeenCalled();
  });

  it("updates transcript when Voice.onSpeechResults fires", async () => {
    const { result } = renderHook(() => useVoiceRecognition());

    await act(async () => {
      await result.current.startListening();
    });

    act(() => {
      _simulateSpeechResults(["hello world"]);
    });

    expect(result.current.transcript).toBe("hello world");
  });

  it("sets error and stops listening when Voice.onSpeechError fires", async () => {
    const { result } = renderHook(() => useVoiceRecognition());

    await act(async () => {
      await result.current.startListening();
    });

    act(() => {
      _simulateSpeechError("Recognition failed");
    });

    expect(result.current.error).toBe("Recognition failed");
    expect(result.current.isListening).toBe(false);
  });

  it("resetTranscript clears transcript and error", async () => {
    const { result } = renderHook(() => useVoiceRecognition());

    await act(async () => {
      await result.current.startListening();
    });

    act(() => {
      _simulateSpeechResults(["some text"]);
    });
    expect(result.current.transcript).toBe("some text");

    act(() => {
      result.current.resetTranscript();
    });

    expect(result.current.transcript).toBe("");
    expect(result.current.error).toBeNull();
  });

  it("sets isAvailable false when Voice.isAvailable rejects", async () => {
    mockVoice.isAvailable.mockRejectedValue(new Error("not available"));

    const { result, rerender } = renderHook(() => useVoiceRecognition());

    // Wait for the isAvailable check to resolve
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    rerender({});

    expect(result.current.isAvailable).toBe(false);
  });
});
