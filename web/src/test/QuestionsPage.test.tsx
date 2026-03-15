import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import QuestionsPage from "@/pages/QuestionsPage";

vi.mock("@/api/questions", () => ({
  fetchAllQuestions: vi.fn(),
  answerQuestion: vi.fn(),
}));

import { fetchAllQuestions } from "@/api/questions";
const mockFetchAllQuestions = vi.mocked(fetchAllQuestions);

const mockQuestions = [
  {
    id: "q1",
    session_id: "s1",
    question: "Unanswered question",
    context: null,
    answered: false,
    answer: null,
    created_at: "2026-03-15T10:00:00Z",
  },
  {
    id: "q2",
    session_id: "s2",
    question: "Answered question",
    context: null,
    answered: true,
    answer: "The answer",
    created_at: "2026-03-15T09:00:00Z",
  },
];

describe("QuestionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a heading", async () => {
    mockFetchAllQuestions.mockResolvedValue([]);
    render(<QuestionsPage />);
    expect(
      screen.getByRole("heading", { name: /pending questions/i }),
    ).toBeInTheDocument();
  });

  it("fetches questions via fetchAllQuestions and renders QuestionCard for each", async () => {
    mockFetchAllQuestions.mockResolvedValue(mockQuestions);
    render(<QuestionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Unanswered question")).toBeInTheDocument();
    });
    expect(screen.getByText("Answered question")).toBeInTheDocument();
    expect(mockFetchAllQuestions).toHaveBeenCalled();
  });

  it("unanswered questions appear before answered questions in the list", async () => {
    // Give answered question an earlier id but answered=true, unanswered later
    const questions = [
      {
        id: "q-answered",
        session_id: "s1",
        question: "Already answered",
        context: null,
        answered: true,
        answer: "Yes",
        created_at: "2026-03-15T08:00:00Z",
      },
      {
        id: "q-unanswered",
        session_id: "s2",
        question: "Still pending",
        context: null,
        answered: false,
        answer: null,
        created_at: "2026-03-15T10:00:00Z",
      },
    ];
    mockFetchAllQuestions.mockResolvedValue(questions);
    render(<QuestionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Still pending")).toBeInTheDocument();
    });

    const cards = screen.getAllByText(/Still pending|Already answered/);
    expect(cards[0].textContent).toBe("Still pending");
    expect(cards[1].textContent).toBe("Already answered");
  });

  it("shows loading state while fetching", () => {
    mockFetchAllQuestions.mockReturnValue(new Promise(() => {}));
    render(<QuestionsPage />);
    expect(screen.getByText("Loading questions...")).toBeInTheDocument();
  });

  it("shows empty state when no questions exist", async () => {
    mockFetchAllQuestions.mockResolvedValue([]);
    render(<QuestionsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No pending questions across any session."),
      ).toBeInTheDocument();
    });
  });

  it("shows error state when fetch fails", async () => {
    mockFetchAllQuestions.mockRejectedValue(
      new Error("Failed to fetch questions: 500"),
    );
    render(<QuestionsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch questions: 500"),
      ).toBeInTheDocument();
    });
  });
});
