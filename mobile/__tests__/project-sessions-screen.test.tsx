import React from "react";
import { render, screen, waitFor } from "@testing-library/react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { DashboardStackParamList } from "../src/navigation/types";
import ProjectSessionsScreen from "../src/screens/ProjectSessionsScreen";
import { listSessions } from "../src/api/sessions";

jest.mock("../src/api/sessions");
const mockListSessions = listSessions as jest.MockedFunction<
  typeof listSessions
>;

const Stack = createNativeStackNavigator<DashboardStackParamList>();

function renderWithNavigation() {
  // Dummy placeholder for DashboardHome
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="ProjectSessions"
      >
        <Stack.Screen name="DashboardHome" component={Placeholder} />
        <Stack.Screen
          name="ProjectSessions"
          component={ProjectSessionsScreen}
          initialParams={{ projectId: "p1", projectName: "Test Project" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

describe("ProjectSessionsScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders sessions from the API", async () => {
    mockListSessions.mockResolvedValue([
      {
        id: "s1",
        name: "Session One",
        mode: "execution",
        status: "idle",
        updated_at: new Date().toISOString(),
      },
      {
        id: "s2",
        name: "Session Two",
        mode: "planning",
        status: "planning",
        updated_at: new Date().toISOString(),
      },
      {
        id: "s3",
        name: "Session Three",
        mode: "review",
        status: "completed",
        updated_at: new Date().toISOString(),
      },
    ]);

    renderWithNavigation();

    await waitFor(() => {
      expect(screen.getByText("Session One")).toBeTruthy();
      expect(screen.getByText("Session Two")).toBeTruthy();
      expect(screen.getByText("Session Three")).toBeTruthy();
    });

    expect(mockListSessions).toHaveBeenCalledWith("p1");
  });

  it("shows empty state when no sessions", async () => {
    mockListSessions.mockResolvedValue([]);

    renderWithNavigation();

    await waitFor(() => {
      expect(screen.getByText("No sessions yet")).toBeTruthy();
    });
  });
});
