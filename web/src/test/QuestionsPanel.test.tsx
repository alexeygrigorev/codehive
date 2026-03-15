import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import QuestionsPanel from "@/components/sidebar/QuestionsPanel";

vi.mock("@/api/questions", () => ({
  fetchSessionQuestions: vi.fn(),
  answerQuestion: vi.fn(),
}));

import { fetchSessionQuestions } from "@/api/questions";
const mockFetchSessionQuestions = vi.mocked(fetchSessionQuestions);

const mockQuestions = [
  {
    id: "q1",
    session_id: "s1",
    question: "What database?",
    context: null,
    answered: false,
    answer: null,
    created_at: "2026-03-15T10:00:00Z",
  },
  {
    id: "q2",
    session_id: "s1",
    question: "Which ORM?",
    context: null,
    answered: true,
    answer: "SQLAlchemy",
    created_at: "2026-03-15T09:00:00Z",
  },
];

describe("QuestionsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches questions via fetchSessionQuestions and renders QuestionCard for each", async () => {
    mockFetchSessionQuestions.mockResolvedValue(mockQuestions);
    render(<QuestionsPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("What database?")).toBeInTheDocument();
    });
    expect(screen.getByText("Which ORM?")).toBeInTheDocument();
    expect(mockFetchSessionQuestions).toHaveBeenCalledWith("s1");
  });

  it("shows loading state while fetching", () => {
    mockFetchSessionQuestions.mockReturnValue(new Promise(() => {}));
    render(<QuestionsPanel sessionId="s1" />);
    expect(screen.getByText("Loading questions...")).toBeInTheDocument();
  });

  it("shows empty state when no questions exist", async () => {
    mockFetchSessionQuestions.mockResolvedValue([]);
    render(<QuestionsPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("No pending questions")).toBeInTheDocument();
    });
  });

  it("shows error state when fetch fails", async () => {
    mockFetchSessionQuestions.mockRejectedValue(
      new Error("Failed to fetch session questions: 500"),
    );
    render(<QuestionsPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch session questions: 500"),
      ).toBeInTheDocument();
    });
  });
});
