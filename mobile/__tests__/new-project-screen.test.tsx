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
import NewProjectScreen from "../src/screens/NewProjectScreen";
import { startFlow } from "../src/api/projectFlow";

jest.mock("../src/api/projectFlow");
const mockStartFlow = startFlow as jest.MockedFunction<typeof startFlow>;

const Stack = createNativeStackNavigator<DashboardStackParamList>();

function renderWithNavigation() {
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="NewProject" component={NewProjectScreen} />
        <Stack.Screen name="FlowChat" component={Placeholder} />
        <Stack.Screen name="BriefReview" component={Placeholder} />
        <Stack.Screen name="ProjectSessions" component={Placeholder} />
      </Stack.Navigator>
    </NavigationContainer>,
  );
}

const ASYNC_TIMEOUT = 15000;

describe("NewProjectScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it(
    "renders four flow type cards with expected titles",
    () => {
      renderWithNavigation();

      expect(screen.getByText("Brainstorm")).toBeTruthy();
      expect(screen.getByText("Guided Interview")).toBeTruthy();
      expect(screen.getByText("From Notes")).toBeTruthy();
      expect(screen.getByText("From Repository")).toBeTruthy();
    },
    ASYNC_TIMEOUT,
  );

  it(
    "each card has a description text",
    () => {
      renderWithNavigation();

      expect(
        screen.getByText("Free-form ideation to explore your project idea"),
      ).toBeTruthy();
      expect(
        screen.getByText(
          "Structured questions to define your requirements",
        ),
      ).toBeTruthy();
      expect(
        screen.getByText(
          "Start from existing notes or a project description",
        ),
      ).toBeTruthy();
      expect(
        screen.getByText("Import and analyze an existing repository"),
      ).toBeTruthy();
    },
    ASYNC_TIMEOUT,
  );

  it(
    "tapping Brainstorm card calls startFlow with flow_type brainstorm",
    async () => {
      mockStartFlow.mockResolvedValue({
        flow_id: "f1",
        session_id: "s1",
        first_questions: [
          { id: "q1", text: "What?", category: "General" },
        ],
      });

      renderWithNavigation();

      fireEvent.press(screen.getByTestId("flow-card-brainstorm"));

      await waitFor(
        () => {
          expect(mockStartFlow).toHaveBeenCalledWith({
            flow_type: "brainstorm",
            initial_input: undefined,
          });
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "tapping From Notes card shows TextInput and Continue button without calling startFlow",
    () => {
      renderWithNavigation();

      fireEvent.press(screen.getByTestId("flow-card-from_notes"));

      expect(screen.getByTestId("initial-input")).toBeTruthy();
      expect(screen.getByTestId("continue-button")).toBeTruthy();
      expect(mockStartFlow).not.toHaveBeenCalled();
    },
    ASYNC_TIMEOUT,
  );

  it(
    "Continue button is disabled when initial input is empty",
    () => {
      renderWithNavigation();

      fireEvent.press(screen.getByTestId("flow-card-from_notes"));

      const continueButton = screen.getByTestId("continue-button");
      // The button should be disabled (TouchableOpacity with disabled prop)
      expect(continueButton.props.accessibilityState?.disabled).toBe(true);
    },
    ASYNC_TIMEOUT,
  );

  it(
    "shows ActivityIndicator while startFlow is pending",
    async () => {
      // Never resolve to keep loading state
      mockStartFlow.mockReturnValue(new Promise(() => {}));

      renderWithNavigation();

      fireEvent.press(screen.getByTestId("flow-card-brainstorm"));

      await waitFor(
        () => {
          expect(screen.getByTestId("loading-indicator")).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "shows error message when startFlow rejects",
    async () => {
      mockStartFlow.mockRejectedValue(new Error("Network error"));

      renderWithNavigation();

      fireEvent.press(screen.getByTestId("flow-card-brainstorm"));

      await waitFor(
        () => {
          expect(screen.getByTestId("error-message")).toBeTruthy();
          expect(
            screen.getByText(
              "Failed to start project flow. Please try again.",
            ),
          ).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );
});
