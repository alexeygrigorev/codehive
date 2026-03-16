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
import FlowChatScreen from "../src/screens/FlowChatScreen";
import { respondToFlow } from "../src/api/projectFlow";

jest.mock("../src/api/projectFlow");
const mockRespondToFlow = respondToFlow as jest.MockedFunction<
  typeof respondToFlow
>;

const Stack = createNativeStackNavigator<DashboardStackParamList>();

const MOCK_QUESTIONS = [
  { id: "q1", text: "What is the project about?", category: "General" },
  { id: "q2", text: "Who is the target audience?", category: "General" },
  { id: "q3", text: "What tech stack?", category: "Technical" },
];

function renderWithNavigation(
  questions = MOCK_QUESTIONS,
  flowId = "flow-1",
) {
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen
          name="FlowChat"
          component={FlowChatScreen}
          initialParams={{ flowId, questions }}
        />
        <Stack.Screen name="BriefReview" component={Placeholder} />
        <Stack.Screen name="ProjectSessions" component={Placeholder} />
      </Stack.Navigator>
    </NavigationContainer>,
  );
}

const ASYNC_TIMEOUT = 15000;

describe("FlowChatScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it(
    "renders one TextInput per question passed via navigation params",
    () => {
      renderWithNavigation();

      expect(screen.getByTestId("answer-q1")).toBeTruthy();
      expect(screen.getByTestId("answer-q2")).toBeTruthy();
      expect(screen.getByTestId("answer-q3")).toBeTruthy();
    },
    ASYNC_TIMEOUT,
  );

  it(
    "displays question text as label above each TextInput",
    () => {
      renderWithNavigation();

      expect(
        screen.getByText("What is the project about?"),
      ).toBeTruthy();
      expect(
        screen.getByText("Who is the target audience?"),
      ).toBeTruthy();
      expect(screen.getByText("What tech stack?")).toBeTruthy();
    },
    ASYNC_TIMEOUT,
  );

  it(
    "Submit button calls respondToFlow with correctly shaped answers payload",
    async () => {
      mockRespondToFlow.mockResolvedValue({
        next_questions: null,
        brief: {
          name: "My Project",
          description: "Desc",
          tech_stack: [],
          architecture: "",
          open_decisions: [],
          suggested_sessions: [],
        },
      });

      renderWithNavigation();

      fireEvent.changeText(screen.getByTestId("answer-q1"), "A task manager");
      fireEvent.changeText(screen.getByTestId("answer-q2"), "Developers");

      fireEvent.press(screen.getByTestId("submit-button"));

      await waitFor(
        () => {
          expect(mockRespondToFlow).toHaveBeenCalledWith("flow-1", [
            { question_id: "q1", answer: "A task manager" },
            { question_id: "q2", answer: "Developers" },
            { question_id: "q3", answer: "" },
          ]);
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "shows ActivityIndicator during submit",
    async () => {
      mockRespondToFlow.mockReturnValue(new Promise(() => {}));

      renderWithNavigation();

      fireEvent.press(screen.getByTestId("submit-button"));

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
    "when response has next_questions, re-renders with new question TextInputs",
    async () => {
      const newQuestions = [
        { id: "q4", text: "Follow-up question?", category: "Details" },
      ];
      mockRespondToFlow.mockResolvedValue({
        next_questions: newQuestions,
        brief: null,
      });

      renderWithNavigation();

      fireEvent.press(screen.getByTestId("submit-button"));

      await waitFor(
        () => {
          expect(screen.getByText("Follow-up question?")).toBeTruthy();
          expect(screen.getByTestId("answer-q4")).toBeTruthy();
        },
        { timeout: 5000 },
      );

      // Old questions should be gone
      expect(screen.queryByTestId("answer-q1")).toBeNull();
    },
    ASYNC_TIMEOUT,
  );

  it(
    "shows error message when respondToFlow rejects",
    async () => {
      mockRespondToFlow.mockRejectedValue(new Error("Server error"));

      renderWithNavigation();

      fireEvent.press(screen.getByTestId("submit-button"));

      await waitFor(
        () => {
          expect(screen.getByTestId("error-message")).toBeTruthy();
          expect(
            screen.getByText(
              "Failed to submit answers. Please try again.",
            ),
          ).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "displays category labels",
    () => {
      renderWithNavigation();

      expect(screen.getByTestId("category-General")).toBeTruthy();
      expect(screen.getByTestId("category-Technical")).toBeTruthy();
    },
    ASYNC_TIMEOUT,
  );
});
