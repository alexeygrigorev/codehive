import React from "react";
import {
  render,
  screen,
  fireEvent,
  act,
  waitFor,
} from "@testing-library/react-native";
import VoiceButton from "../src/components/VoiceButton";
import Voice from "@react-native-voice/voice";
import { _simulateSpeechResults } from "../__mocks__/@react-native-voice/voice";

jest.mock("@react-native-voice/voice");

const mockVoice = Voice as jest.Mocked<typeof Voice>;

describe("VoiceButton", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockVoice.isAvailable.mockResolvedValue(1);
    mockVoice.start.mockResolvedValue(undefined);
    mockVoice.stop.mockResolvedValue(undefined);
  });

  it("renders a touchable element with testID voice-button", async () => {
    const onTranscript = jest.fn();
    render(<VoiceButton onTranscript={onTranscript} />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });
  });

  it("tapping the button when idle starts listening", async () => {
    const onTranscript = jest.fn();
    render(<VoiceButton onTranscript={onTranscript} />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    expect(mockVoice.start).toHaveBeenCalledWith("en-US");
  });

  it("tapping the button when listening stops listening", async () => {
    const onTranscript = jest.fn();
    render(<VoiceButton onTranscript={onTranscript} />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    // Start listening
    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    // Stop listening
    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    expect(mockVoice.stop).toHaveBeenCalled();
  });

  it("shows different visual indicator when listening vs idle", async () => {
    const onTranscript = jest.fn();
    render(<VoiceButton onTranscript={onTranscript} />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    // Idle state shows "Mic"
    expect(screen.getByText("Mic")).toBeTruthy();
    expect(screen.queryByTestId("listening-label")).toBeNull();

    // Start listening
    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    // Listening state shows "Stop" and "Listening..." label
    expect(screen.getByText("Stop")).toBeTruthy();
    expect(screen.getByTestId("listening-label")).toBeTruthy();
  });

  it("calls onTranscript callback when speech recognition produces a result", async () => {
    const onTranscript = jest.fn();
    render(<VoiceButton onTranscript={onTranscript} />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    act(() => {
      _simulateSpeechResults(["hello from voice"]);
    });

    await waitFor(() => {
      expect(onTranscript).toHaveBeenCalledWith("hello from voice");
    });
  });

  it("does not render when speech recognition is unavailable", async () => {
    mockVoice.isAvailable.mockResolvedValue(0);
    const onTranscript = jest.fn();

    render(<VoiceButton onTranscript={onTranscript} />);

    // Wait for the isAvailable check to resolve and component to update
    await waitFor(() => {
      expect(screen.queryByTestId("voice-button")).toBeNull();
    });
  });

  it("respects disabled prop and does not respond to taps", async () => {
    const onTranscript = jest.fn();
    render(<VoiceButton onTranscript={onTranscript} disabled />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    expect(mockVoice.start).not.toHaveBeenCalled();
  });
});
