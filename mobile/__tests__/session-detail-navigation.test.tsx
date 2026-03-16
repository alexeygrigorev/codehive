import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from "@testing-library/react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { DashboardStackParamList } from "../src/navigation/types";
import ProjectSessionsScreen from "../src/screens/ProjectSessionsScreen";
import SessionDetailScreen from "../src/screens/SessionDetailScreen";
import { listSessions, getSession, getMessages } from "../src/api/sessions";
import { useEvents } from "../src/context/EventContext";

jest.mock("../src/api/sessions");
jest.mock("../src/context/EventContext");

const mockListSessions = listSessions as jest.MockedFunction<
  typeof listSessions
>;
const mockGetSession = getSession as jest.MockedFunction<typeof getSession>;
const mockGetMessages = getMessages as jest.MockedFunction<typeof getMessages>;
const mockUseEvents = useEvents as jest.MockedFunction<typeof useEvents>;

const Stack = createNativeStackNavigator<DashboardStackParamList>();

function Placeholder() {
  return null;
}

function renderWithNavigation() {
  mockUseEvents.mockReturnValue({
    lastEvent: null,
    connect: jest.fn(),
    disconnect: jest.fn(),
    addListener: jest.fn(),
    removeListener: jest.fn(),
  });

  return render(
    <NavigationContainer>
      <Stack.Navigator initialRouteName="ProjectSessions">
        <Stack.Screen name="DashboardHome" component={Placeholder} />
        <Stack.Screen
          name="ProjectSessions"
          component={ProjectSessionsScreen}
          initialParams={{ projectId: "p1", projectName: "Test Project" }}
        />
        <Stack.Screen
          name="SessionDetail"
          component={SessionDetailScreen}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

describe("Navigation: SessionCard -> SessionDetail", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("navigates from ProjectSessionsScreen to SessionDetailScreen on card tap", async () => {
    mockListSessions.mockResolvedValue([
      {
        id: "s1",
        name: "Auth Session",
        mode: "execution",
        status: "executing",
        updated_at: new Date().toISOString(),
      },
    ]);

    mockGetSession.mockResolvedValue({
      id: "s1",
      name: "Auth Session",
      mode: "execution",
      status: "executing",
    });
    mockGetMessages.mockResolvedValue([
      {
        id: "m1",
        role: "user",
        content: "Fix login",
        created_at: "2026-03-16T10:00:00Z",
      },
    ]);

    renderWithNavigation();

    // Wait for sessions to load
    await waitFor(() => {
      expect(screen.getByText("Auth Session")).toBeTruthy();
    });

    // Tap the session card
    fireEvent.press(screen.getByTestId("session-card"));

    // Should navigate to SessionDetailScreen and show the session detail
    await waitFor(() => {
      expect(mockGetSession).toHaveBeenCalledWith("s1");
      expect(screen.getByText("Fix login")).toBeTruthy();
    });
  });
});
