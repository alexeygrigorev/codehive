import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import QuestionCard from "@/components/QuestionCard";

vi.mock("@/api/questions", () => ({
  answerQuestion: vi.fn(),
}));

import { answerQuestion } from "@/api/questions";
const mockAnswerQuestion = vi.mocked(answerQuestion);

const unansweredQuestion = {
  id: "q1",
  session_id: "s1",
  question: "What database should we use?",
  context: "We need to choose between PostgreSQL and MySQL",
  answered: false,
  answer: null,
  created_at: "2026-03-15T10:00:00Z",
};

const answeredQuestion = {
  id: "q2",
  session_id: "s1",
  question: "Which framework?",
  context: null,
  answered: true,
  answer: "Use FastAPI",
  created_at: "2026-03-15T09:00:00Z",
};

describe("QuestionCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders question text and context", () => {
    render(<QuestionCard question={unansweredQuestion} />);
    expect(
      screen.getByText("What database should we use?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("We need to choose between PostgreSQL and MySQL"),
    ).toBeInTheDocument();
  });

  it("renders relative timestamp", () => {
    render(<QuestionCard question={unansweredQuestion} />);
    // The timestamp will be some relative time -- just check it renders something
    const timeElements = screen.getAllByText(
      /just now|minutes? ago|hours? ago|days? ago/,
    );
    expect(timeElements.length).toBeGreaterThan(0);
  });

  it('shows "Unanswered" badge for unanswered questions', () => {
    render(<QuestionCard question={unansweredQuestion} />);
    expect(screen.getByText("Unanswered")).toBeInTheDocument();
  });

  it('shows "Answered" badge for answered questions', () => {
    render(<QuestionCard question={answeredQuestion} />);
    expect(screen.getByText("Answered")).toBeInTheDocument();
  });

  it("renders textarea and submit button for unanswered questions", () => {
    render(<QuestionCard question={unansweredQuestion} />);
    expect(
      screen.getByPlaceholderText("Type your answer..."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /submit answer/i }),
    ).toBeInTheDocument();
  });

  it("does not render textarea or submit button for answered questions", () => {
    render(<QuestionCard question={answeredQuestion} />);
    expect(
      screen.queryByPlaceholderText("Type your answer..."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /submit answer/i }),
    ).not.toBeInTheDocument();
  });

  it("displays the answer text for answered questions", () => {
    render(<QuestionCard question={answeredQuestion} />);
    expect(screen.getByText("Use FastAPI")).toBeInTheDocument();
  });

  it("submit button is disabled when textarea is empty", () => {
    render(<QuestionCard question={unansweredQuestion} />);
    const button = screen.getByRole("button", { name: /submit answer/i });
    expect(button).toBeDisabled();
  });

  it("submitting an answer calls answerQuestion with correct arguments", async () => {
    const user = userEvent.setup();
    mockAnswerQuestion.mockResolvedValue({
      ...unansweredQuestion,
      answered: true,
      answer: "PostgreSQL",
    });

    render(<QuestionCard question={unansweredQuestion} />);

    const textarea = screen.getByPlaceholderText("Type your answer...");
    await user.type(textarea, "PostgreSQL");

    const button = screen.getByRole("button", { name: /submit answer/i });
    expect(button).not.toBeDisabled();
    await user.click(button);

    expect(mockAnswerQuestion).toHaveBeenCalledWith("s1", "q1", "PostgreSQL");
  });

  it("after successful answer submission, card shows answered state with answer text", async () => {
    const user = userEvent.setup();
    mockAnswerQuestion.mockResolvedValue({
      ...unansweredQuestion,
      answered: true,
      answer: "PostgreSQL",
    });

    render(<QuestionCard question={unansweredQuestion} />);

    const textarea = screen.getByPlaceholderText("Type your answer...");
    await user.type(textarea, "PostgreSQL");
    await user.click(
      screen.getByRole("button", { name: /submit answer/i }),
    );

    await waitFor(() => {
      expect(screen.getByText("Answered")).toBeInTheDocument();
    });
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("Type your answer..."),
    ).not.toBeInTheDocument();
  });

  it("when answerQuestion rejects, an error message is displayed", async () => {
    const user = userEvent.setup();
    mockAnswerQuestion.mockRejectedValue(
      new Error("Failed to answer question: 409"),
    );

    render(<QuestionCard question={unansweredQuestion} />);

    const textarea = screen.getByPlaceholderText("Type your answer...");
    await user.type(textarea, "PostgreSQL");
    await user.click(
      screen.getByRole("button", { name: /submit answer/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByText("Failed to answer question: 409"),
      ).toBeInTheDocument();
    });
  });
});
