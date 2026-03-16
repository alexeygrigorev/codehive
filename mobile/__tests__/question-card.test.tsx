import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import QuestionCard, {
  type Question,
} from "../src/components/QuestionCard";

const unansweredQuestion: Question = {
  id: "q1",
  session_id: "s1",
  question: "Which database should we use?",
  answered: false,
  created_at: "2026-03-15T10:00:00Z",
};

const answeredQuestion: Question = {
  id: "q2",
  session_id: "s2",
  question: "What testing framework?",
  answered: true,
  answer: "Use pytest",
  created_at: "2026-03-15T09:00:00Z",
};

describe("QuestionCard", () => {
  it("renders unanswered question with text, session ID, and input", () => {
    const onAnswer = jest.fn();
    render(<QuestionCard question={unansweredQuestion} onAnswer={onAnswer} />);

    expect(
      screen.getByText("Which database should we use?"),
    ).toBeTruthy();
    expect(screen.getByText("Session: s1")).toBeTruthy();
    expect(screen.getByTestId("answer-input")).toBeTruthy();
    expect(screen.getByTestId("submit-answer")).toBeTruthy();
  });

  it("calls onAnswer with correct id and answer text on submit", () => {
    const onAnswer = jest.fn();
    render(<QuestionCard question={unansweredQuestion} onAnswer={onAnswer} />);

    fireEvent.changeText(screen.getByTestId("answer-input"), "PostgreSQL");
    fireEvent.press(screen.getByTestId("submit-answer"));

    expect(onAnswer).toHaveBeenCalledWith("q1", "PostgreSQL");
  });

  it("renders answered question with answer text and no input", () => {
    const onAnswer = jest.fn();
    render(<QuestionCard question={answeredQuestion} onAnswer={onAnswer} />);

    expect(screen.getByText("What testing framework?")).toBeTruthy();
    expect(screen.getByText("Use pytest")).toBeTruthy();
    expect(screen.queryByTestId("answer-input")).toBeNull();
  });

  it("disables submit button when input is empty", () => {
    const onAnswer = jest.fn();
    render(<QuestionCard question={unansweredQuestion} onAnswer={onAnswer} />);

    const submitButton = screen.getByTestId("submit-answer");
    fireEvent.press(submitButton);

    expect(onAnswer).not.toHaveBeenCalled();
  });
});
