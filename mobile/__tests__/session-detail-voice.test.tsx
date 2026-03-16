import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { SessionsStackParamList } from "../src/navigation/types";
import SessionDetailScreen from "../src/screens/SessionDetailScreen";
import { getSession, getMessages, sendMessage } from "../src/api/sessions";
import { useEvents } from "../src/context/EventContext";
import Voice from "@react-native-voice/voice";
import { _simulateSpeechResults } from "../__mocks__/@react-native-voice/voice";

jest.mock("../src/api/sessions");
jest.mock("../src/context/EventContext");
jest.mock("@react-native-voice/voice");

const mockGetSession = getSession as jest.MockedFunction<typeof getSession>;
const mockGetMessages = getMessages as jest.MockedFunction<typeof getMessages>;
const mockSendMessage = sendMessage as jest.MockedFunction<typeof sendMessage>;
const mockUseEvents = useEvents as jest.MockedFunction<typeof useEvents>;
const mockVoice = Voice as jest.Mocked<typeof Voice>;

const Stack = createNativeStackNavigator<SessionsStackParamList>();

function setupMocks() {
  const mockEvents = {
    lastEvent: null,
    connect: jest.fn(),
    disconnect: jest.fn(),
    addListener: jest.fn(),
    removeListener: jest.fn(),
  };
  mockUseEvents.mockReturnValue(mockEvents);
  mockVoice.isAvailable.mockResolvedValue(1);
  mockVoice.start.mockResolvedValue(undefined);
  mockVoice.stop.mockResolvedValue(undefined);

  mockGetSession.mockResolvedValue({
    id: "sess-1",
    name: "Voice Test Session",
    mode: "execution",
    status: "idle",
  });
  mockGetMessages.mockResolvedValue([]);
  mockSendMessage.mockResolvedValue({ ok: true });

  return mockEvents;
}

function renderScreen() {
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator initialRouteName="SessionDetail">
        <Stack.Screen name="SessionsList" component={Placeholder} />
        <Stack.Screen
          name="SessionDetail"
          component={SessionDetailScreen}
          initialParams={{ sessionId: "sess-1" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

describe("SessionDetailScreen with voice input", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("voice button is present in the session detail input bar", async () => {
    setupMocks();
    renderScreen();

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });
  });

  it("voice transcript populates the message TextInput", async () => {
    setupMocks();
    renderScreen();

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    // Start listening
    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    // Simulate voice result
    act(() => {
      _simulateSpeechResults(["hello from voice"]);
    });

    await waitFor(() => {
      const input = screen.getByTestId("message-input");
      expect(input.props.value).toBe("hello from voice");
    });
  });

  it("user can edit voice-populated text and send it", async () => {
    setupMocks();
    renderScreen();

    await waitFor(() => {
      expect(screen.getByTestId("voice-button")).toBeTruthy();
    });

    // Start listening and get transcript
    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    act(() => {
      _simulateSpeechResults(["voice text"]);
    });

    await waitFor(() => {
      const input = screen.getByTestId("message-input");
      expect(input.props.value).toBe("voice text");
    });

    // Edit the text
    fireEvent.changeText(screen.getByTestId("message-input"), "voice text edited");

    // Send via the send button
    await act(async () => {
      fireEvent.press(screen.getByTestId("send-button"));
    });

    expect(mockSendMessage).toHaveBeenCalledWith("sess-1", "voice text edited");
  });

  it("sent message goes through the same sendMessage API as typed messages", async () => {
    setupMocks();
    renderScreen();

    await waitFor(() => {
      expect(screen.getByTestId("message-input")).toBeTruthy();
    });

    // Type manually
    fireEvent.changeText(screen.getByTestId("message-input"), "typed message");
    await act(async () => {
      fireEvent.press(screen.getByTestId("send-button"));
    });

    expect(mockSendMessage).toHaveBeenCalledWith("sess-1", "typed message");

    // Now use voice (same API call)
    await act(async () => {
      fireEvent.press(screen.getByTestId("voice-button"));
    });

    act(() => {
      _simulateSpeechResults(["voice message"]);
    });

    await waitFor(() => {
      const input = screen.getByTestId("message-input");
      expect(input.props.value).toBe("voice message");
    });

    await act(async () => {
      fireEvent.press(screen.getByTestId("send-button"));
    });

    // Both calls use same sendMessage function
    expect(mockSendMessage).toHaveBeenCalledTimes(2);
    expect(mockSendMessage).toHaveBeenLastCalledWith("sess-1", "voice message");
  });
});
