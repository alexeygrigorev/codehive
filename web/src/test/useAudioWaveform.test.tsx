import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useAudioWaveform } from "@/hooks/useAudioWaveform";

function createMockMediaStream(): MediaStream {
  const track = {
    stop: vi.fn(),
    kind: "audio",
    id: "mock-track",
    enabled: true,
    muted: false,
    label: "Mock Audio Track",
    readyState: "live" as MediaStreamTrackState,
    contentHint: "",
    onended: null,
    onmute: null,
    onunmute: null,
    clone: vi.fn(),
    getCapabilities: vi.fn(() => ({})),
    getConstraints: vi.fn(() => ({})),
    getSettings: vi.fn(() => ({})),
    applyConstraints: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  } as unknown as MediaStreamTrack;

  return {
    getTracks: vi.fn(() => [track]),
    getAudioTracks: vi.fn(() => [track]),
    getVideoTracks: vi.fn(() => []),
    addTrack: vi.fn(),
    removeTrack: vi.fn(),
    clone: vi.fn(),
    id: "mock-stream",
    active: true,
    onaddtrack: null,
    onremovetrack: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
    getTrackById: vi.fn(),
  } as unknown as MediaStream;
}

const mockAnalyserConnect = vi.fn();
const mockAnalyserGetByteTimeDomainData = vi.fn((arr: Uint8Array) => {
  for (let i = 0; i < arr.length; i++) arr[i] = 128;
});

const mockSourceConnect = vi.fn();
const mockContextClose = vi.fn();
const mockCreateAnalyser = vi.fn();
const mockCreateMediaStreamSource = vi.fn();

describe("useAudioWaveform", () => {
  let mockStream: MediaStream;

  beforeEach(() => {
    vi.useFakeTimers();
    mockStream = createMockMediaStream();

    // Reset mocks
    mockAnalyserConnect.mockClear();
    mockAnalyserGetByteTimeDomainData.mockClear();
    mockSourceConnect.mockClear();
    mockContextClose.mockClear();
    mockCreateAnalyser.mockClear();
    mockCreateMediaStreamSource.mockClear();

    const mockAnalyser = {
      fftSize: 0,
      frequencyBinCount: 128,
      getByteTimeDomainData: mockAnalyserGetByteTimeDomainData,
      connect: mockAnalyserConnect,
      disconnect: vi.fn(),
    };

    const mockSource = {
      connect: mockSourceConnect,
      disconnect: vi.fn(),
    };

    mockCreateAnalyser.mockReturnValue(mockAnalyser);
    mockCreateMediaStreamSource.mockReturnValue(mockSource);

    // Use a class so `new AudioContext()` works
    window.AudioContext = class MockAudioContext {
      createAnalyser = mockCreateAnalyser;
      createMediaStreamSource = mockCreateMediaStreamSource;
      close = mockContextClose;
      state = "running";
    } as unknown as typeof AudioContext;

    if (!navigator.mediaDevices) {
      Object.defineProperty(navigator, "mediaDevices", {
        value: { getUserMedia: vi.fn() },
        writable: true,
        configurable: true,
      });
    }

    navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockResolvedValue(mockStream);

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
  });

  it("initializes with isActive false and null waveform data", () => {
    const { result } = renderHook(() => useAudioWaveform());
    expect(result.current.isActive).toBe(false);
    expect(result.current.waveformData).toBeNull();
    expect(result.current.elapsedSeconds).toBe(0);
    expect(result.current.error).toBeNull();
  });

  it("start() calls getUserMedia and creates AudioContext + AnalyserNode", async () => {
    const { result } = renderHook(() => useAudioWaveform());

    await act(async () => {
      await result.current.start();
    });

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
      audio: true,
    });
    expect(mockCreateAnalyser).toHaveBeenCalled();
    expect(mockCreateMediaStreamSource).toHaveBeenCalledWith(mockStream);
    expect(mockSourceConnect).toHaveBeenCalled();
    expect(result.current.isActive).toBe(true);
  });

  it("stop() closes AudioContext and stops MediaStream tracks", async () => {
    const { result } = renderHook(() => useAudioWaveform());

    await act(async () => {
      await result.current.start();
    });

    act(() => {
      result.current.stop();
    });

    expect(mockContextClose).toHaveBeenCalled();
    expect(mockStream.getTracks()[0].stop).toHaveBeenCalled();
    expect(result.current.isActive).toBe(false);
    expect(result.current.waveformData).toBeNull();
  });

  it("elapsedSeconds increments while active", async () => {
    const { result } = renderHook(() => useAudioWaveform());

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.elapsedSeconds).toBe(0);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.elapsedSeconds).toBe(1);

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current.elapsedSeconds).toBe(3);
  });

  it("handles getUserMedia rejection gracefully", async () => {
    navigator.mediaDevices.getUserMedia = vi
      .fn()
      .mockRejectedValue(new Error("Permission denied"));

    const { result } = renderHook(() => useAudioWaveform());

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.isActive).toBe(false);
    expect(result.current.error).toBe("Permission denied");
  });

  it("handles missing getUserMedia gracefully", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: {},
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useAudioWaveform());

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.isActive).toBe(false);
    expect(result.current.error).toBe(
      "getUserMedia is not supported in this browser",
    );
  });

  it("cleanup on unmount stops all resources", async () => {
    const { result, unmount } = renderHook(() => useAudioWaveform());

    await act(async () => {
      await result.current.start();
    });

    unmount();

    expect(mockContextClose).toHaveBeenCalled();
    expect(mockStream.getTracks()[0].stop).toHaveBeenCalled();
  });
});
