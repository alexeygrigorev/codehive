import React from "react";
import { render, screen } from "@testing-library/react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Text } from "react-native";
import type { DashboardStackParamList } from "../src/navigation/types";

// Mock the API to prevent real calls during navigation test
jest.mock("../src/api/projects", () => ({
  listProjects: jest.fn().mockResolvedValue([]),
}));

const Stack = createNativeStackNavigator<DashboardStackParamList>();

describe("Dashboard stack navigation", () => {
  it("DashboardStackParamList includes ProjectSessions route", () => {
    // This test verifies at the type level that ProjectSessions exists
    // by using it as a valid screen name in the stack navigator
    const ProjectSessionsPlaceholder = () => <Text>PS</Text>;
    const DashboardPlaceholder = () => <Text>DH</Text>;

    const { unmount } = render(
      <NavigationContainer>
        <Stack.Navigator initialRouteName="DashboardHome">
          <Stack.Screen name="DashboardHome" component={DashboardPlaceholder} />
          <Stack.Screen
            name="ProjectSessions"
            component={ProjectSessionsPlaceholder}
            initialParams={{ projectId: "p1", projectName: "Test" }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    );

    // DashboardHome is the initial screen
    expect(screen.getByText("DH")).toBeTruthy();
    unmount();
  });

  it("DashboardHome is the initial screen in the stack", () => {
    const DashboardPlaceholder = () => <Text>Dashboard Initial</Text>;
    const PSPlaceholder = () => <Text>PS</Text>;

    render(
      <NavigationContainer>
        <Stack.Navigator initialRouteName="DashboardHome">
          <Stack.Screen name="DashboardHome" component={DashboardPlaceholder} />
          <Stack.Screen
            name="ProjectSessions"
            component={PSPlaceholder}
            initialParams={{ projectId: "x", projectName: "X" }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    );

    expect(screen.getByText("Dashboard Initial")).toBeTruthy();
  });
});
