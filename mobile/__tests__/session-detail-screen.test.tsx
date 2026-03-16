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

jest.mock("../src/api/sessions");
jest.mock("../src/context/EventContext");

const mockGetSession = getSession as jest.MockedFunction<typeof getSession>;
const mockGetMessages = getMessages as jest.MockedFunction<typeof getMessages>;
const mockSendMessage = sendMessage as jest.MockedFunction<typeof sendMessage>;
const mockUseEvents = useEvents as jest.MockedFunction<typeof useEvents>;

const Stack = createNativeStackNavigator<SessionsStackParamList>();

// Store the event listener so we can simulate WS events
let capturedListener: ((event: unknown) => void) | null = null;

function setupMockEvents() {
  const mockEvents = {
    lastEvent: null,
    connect: jest.fn(),
    disconnect: jest.fn(),
    addListener: jest.fn((handler: (event: unknown) => void) => {
      capturedListener = handler;
    }),
    removeListener: jest.fn(),
  };
  mockUseEvents.mockReturnValue(mockEvents);
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

describe("SessionDetailScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedListener = null;
  });

  it("shows loading state before API resolves", async () => {
    setupMockEvents();
    // Make the API hang
    mockGetSession.mockReturnValue(new Promise(() => {}));
    mockGetMessages.mockReturnValue(new Promise(() => {}));

    renderScreen();

    expect(screen.getByTestId("loading-spinner")).toBeTruthy();
  });

  it("loads and displays session with message history", async () => {
    setupMockEvents();
    mockGetSession.mockResolvedValue({
      id: "sess-1",
      name: "Fix auth bug",
      mode: "execution",
      status: "executing",
    });
    mockGetMessages.mockResolvedValue([
      {
        id: "m1",
        role: "user",
        content: "Fix the login flow",
        created_at: "2026-03-16T10:00:00Z",
      },
      {
        id: "m2",
        role: "assistant",
        content: "I will fix the login flow now.",
        created_at: "2026-03-16T10:00:05Z",
      },
    ]);

    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Fix auth bug")).toBeTruthy();
      expect(screen.getByText("execution")).toBeTruthy();
      expect(screen.getByText("Fix the login flow")).toBeTruthy();
      expect(
        screen.getByText("I will fix the login flow now.")
      ).toBeTruthy();
    });

    expect(mockGetSession).toHaveBeenCalledWith("sess-1");
    expect(mockGetMessages).toHaveBeenCalledWith("sess-1");
  });

  it("sends a message when user types and taps send", async () => {
    setupMockEvents();
    mockGetSession.mockResolvedValue({
      id: "sess-1",
      name: "Test Session",
      mode: "brainstorm",
      status: "idle",
    });
    mockGetMessages.mockResolvedValue([]);
    mockSendMessage.mockResolvedValue({ ok: true });

    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Test Session")).toBeTruthy();
    });

    const input = screen.getByTestId("message-input");
    fireEvent.changeText(input, "Hello agent");
    fireEvent.press(screen.getByTestId("send-button"));

    await waitFor(() => {
      expect(screen.getByText("Hello agent")).toBeTruthy();
    });

    expect(mockSendMessage).toHaveBeenCalledWith("sess-1", "Hello agent");
  });

  it("appends message from WebSocket message.created event", async () => {
    setupMockEvents();
    mockGetSession.mockResolvedValue({
      id: "sess-1",
      name: "WS Test",
      mode: "execution",
      status: "executing",
    });
    mockGetMessages.mockResolvedValue([]);

    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("WS Test")).toBeTruthy();
    });

    // Simulate a WebSocket message.created event
    await act(async () => {
      capturedListener!({
        type: "message.created",
        data: {
          id: "ws-m1",
          role: "assistant",
          content: "Real-time message",
          created_at: "2026-03-16T10:05:00Z",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Real-time message")).toBeTruthy();
    });
  });

  it("updates status badge from WebSocket session.status_changed event", async () => {
    setupMockEvents();
    mockGetSession.mockResolvedValue({
      id: "sess-1",
      name: "Status Test",
      mode: "execution",
      status: "executing",
    });
    mockGetMessages.mockResolvedValue([]);

    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("executing")).toBeTruthy();
    });

    // Simulate a WebSocket session.status_changed event
    await act(async () => {
      capturedListener!({
        type: "session.status_changed",
        data: { status: "completed" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("completed")).toBeTruthy();
    });
  });
});
