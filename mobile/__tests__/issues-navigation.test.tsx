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
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator initialRouteName="ProjectSessions">
        <Stack.Screen name="DashboardHome" component={Placeholder} />
        <Stack.Screen
          name="ProjectSessions"
          component={ProjectSessionsScreen}
          initialParams={{ projectId: "p1", projectName: "Test Project" }}
        />
        <Stack.Screen name="ProjectIssues" component={Placeholder} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

describe("Navigation to Issues", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockListSessions.mockResolvedValue([]);
  });

  it("renders a View Issues button on ProjectSessionsScreen", async () => {
    renderWithNavigation();

    await waitFor(() => {
      expect(screen.getByTestId("view-issues-button")).toBeTruthy();
    });
  });

  it("DashboardStackParamList includes ProjectIssues route", () => {
    // Type-level test: if this compiles, the type includes ProjectIssues
    const params: DashboardStackParamList["ProjectIssues"] = {
      projectId: "p1",
      projectName: "Test",
    };
    expect(params.projectId).toBe("p1");
    expect(params.projectName).toBe("Test");
  });
});
