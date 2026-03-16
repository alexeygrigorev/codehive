import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from "@testing-library/react-native";
import QuestionsScreen from "../src/screens/QuestionsScreen";
import { listQuestions, answerQuestion } from "../src/api/questions";

jest.mock("../src/api/questions");
const mockListQuestions = listQuestions as jest.MockedFunction<
  typeof listQuestions
>;
const mockAnswerQuestion = answerQuestion as jest.MockedFunction<
  typeof answerQuestion
>;

const ASYNC_TIMEOUT = 15000;

describe("QuestionsScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it(
    "renders unanswered questions from the API",
    async () => {
      mockListQuestions.mockResolvedValue([
        {
          id: "q1",
          session_id: "s1",
          question: "Which database?",
          answered: false,
          created_at: "2026-03-15T10:00:00Z",
        },
        {
          id: "q2",
          session_id: "s2",
          question: "Which framework?",
          answered: false,
          created_at: "2026-03-15T11:00:00Z",
        },
      ]);

      render(<QuestionsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("Which database?")).toBeTruthy();
          expect(screen.getByText("Which framework?")).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "shows empty state when no pending questions",
    async () => {
      mockListQuestions.mockResolvedValue([]);

      render(<QuestionsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("No pending questions")).toBeTruthy();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "filters out already-answered questions",
    async () => {
      mockListQuestions.mockResolvedValue([
        {
          id: "q1",
          session_id: "s1",
          question: "Unanswered Q",
          answered: false,
          created_at: "2026-03-15T10:00:00Z",
        },
        {
          id: "q2",
          session_id: "s2",
          question: "Already answered Q",
          answered: true,
          answer: "Done",
          created_at: "2026-03-15T09:00:00Z",
        },
      ]);

      render(<QuestionsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("Unanswered Q")).toBeTruthy();
          expect(screen.queryByText("Already answered Q")).toBeNull();
        },
        { timeout: 5000 },
      );
    },
    ASYNC_TIMEOUT,
  );

  it(
    "calls answerQuestion and removes the card on submit",
    async () => {
      mockListQuestions.mockResolvedValue([
        {
          id: "q1",
          session_id: "s1",
          question: "Which database?",
          answered: false,
          created_at: "2026-03-15T10:00:00Z",
        },
      ]);
      mockAnswerQuestion.mockResolvedValue({});

      render(<QuestionsScreen />);

      await waitFor(
        () => {
          expect(screen.getByText("Which database?")).toBeTruthy();
        },
        { timeout: 5000 },
      );

      fireEvent.changeText(screen.getByTestId("answer-input"), "PostgreSQL");
      fireEvent.press(screen.getByTestId("submit-answer"));

      await waitFor(() => {
        expect(mockAnswerQuestion).toHaveBeenCalledWith("q1", "PostgreSQL");
      });

      await waitFor(() => {
        expect(screen.queryByText("Which database?")).toBeNull();
      });
    },
    ASYNC_TIMEOUT,
  );
});
