import React from "react";
import { render, screen, waitFor } from "@testing-library/react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { DashboardStackParamList } from "../src/navigation/types";
import ProjectIssuesScreen from "../src/screens/ProjectIssuesScreen";
import { listIssues } from "../src/api/issues";

jest.mock("../src/api/issues");
const mockListIssues = listIssues as jest.MockedFunction<typeof listIssues>;

const Stack = createNativeStackNavigator<DashboardStackParamList>();

function renderWithNavigation() {
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator initialRouteName="ProjectIssues">
        <Stack.Screen name="DashboardHome" component={Placeholder} />
        <Stack.Screen
          name="ProjectIssues"
          component={ProjectIssuesScreen}
          initialParams={{ projectId: "p1", projectName: "Test Project" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

describe("ProjectIssuesScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders issues from the API", async () => {
    mockListIssues.mockResolvedValue([
      {
        id: "i1",
        title: "Fix login bug",
        status: "open",
        created_at: new Date().toISOString(),
      },
      {
        id: "i2",
        title: "Add dark mode",
        status: "in_progress",
        created_at: new Date().toISOString(),
      },
    ]);

    renderWithNavigation();

    await waitFor(() => {
      expect(screen.getByText("Fix login bug")).toBeTruthy();
      expect(screen.getByText("Add dark mode")).toBeTruthy();
    });

    expect(mockListIssues).toHaveBeenCalledWith("p1");
  });

  it("shows empty state when no issues", async () => {
    mockListIssues.mockResolvedValue([]);

    renderWithNavigation();

    await waitFor(() => {
      expect(screen.getByText("No issues yet")).toBeTruthy();
    });
  });

  it("shows loading spinner initially", async () => {
    let resolvePromise: (value: unknown[]) => void;
    const promise = new Promise<unknown[]>((resolve) => {
      resolvePromise = resolve;
    });
    mockListIssues.mockReturnValue(promise);

    renderWithNavigation();

    expect(screen.getByTestId("loading-spinner")).toBeTruthy();

    resolvePromise!([
      {
        id: "i1",
        title: "Test issue",
        status: "open",
        created_at: new Date().toISOString(),
      },
    ]);

    await waitFor(() => {
      expect(screen.getByText("Test issue")).toBeTruthy();
    });
  });
});
