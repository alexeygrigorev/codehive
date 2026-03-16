import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import NewProjectPage from "@/pages/NewProjectPage";

vi.mock("@/api/projectFlow", () => ({
  startFlow: vi.fn(),
  respondToFlow: vi.fn(),
  finalizeFlow: vi.fn(),
}));

import { startFlow, respondToFlow, finalizeFlow } from "@/api/projectFlow";

const mockStartFlow = vi.mocked(startFlow);
const mockRespondToFlow = vi.mocked(respondToFlow);
const mockFinalizeFlow = vi.mocked(finalizeFlow);

function renderPage() {
  return render(
    <MemoryRouter>
      <NewProjectPage />
    </MemoryRouter>,
  );
}

describe("NewProjectFlow integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("full wizard flow: select -> chat -> review -> finalize", async () => {
    const user = userEvent.setup();

    // Step 1: startFlow returns questions
    mockStartFlow.mockResolvedValue({
      flow_id: "f1",
      session_id: "s1",
      first_questions: [
        { id: "q1", text: "What are your goals?", category: "goals" },
        { id: "q2", text: "What tech do you prefer?", category: "tech" },
      ],
    });

    renderPage();

    // Select Guided Interview
    await user.click(screen.getByText("Guided Interview"));

    await waitFor(() => {
      expect(mockStartFlow).toHaveBeenCalledWith(
        expect.objectContaining({ flow_type: "interview" }),
      );
    });

    // Step 2: Answer questions
    await waitFor(() => {
      expect(screen.getByLabelText("What are your goals?")).toBeInTheDocument();
    });

    // Mock respond to return brief
    const brief = {
      name: "Interview Project",
      description: "A project from interview",
      tech_stack: ["Python", "FastAPI"],
      architecture: "Microservices",
      open_decisions: ["Cloud provider"],
      suggested_sessions: [
        {
          name: "API Design",
          mission: "Design REST endpoints",
          mode: "planning",
        },
      ],
    };
    mockRespondToFlow.mockResolvedValue({
      next_questions: null,
      brief,
    });

    await user.type(
      screen.getByLabelText("What are your goals?"),
      "Build a platform",
    );
    await user.type(
      screen.getByLabelText("What tech do you prefer?"),
      "Python",
    );
    await user.click(screen.getByText("Submit Answers"));

    await waitFor(() => {
      expect(mockRespondToFlow).toHaveBeenCalledWith("f1", [
        { question_id: "q1", answer: "Build a platform" },
        { question_id: "q2", answer: "Python" },
      ]);
    });

    // Step 3: Review brief
    await waitFor(() => {
      expect(screen.getByText("Review Project Brief")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Project Name")).toHaveValue(
      "Interview Project",
    );
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
    expect(screen.getByText("Microservices")).toBeInTheDocument();
    expect(screen.getByText("Cloud provider")).toBeInTheDocument();
    expect(screen.getByText("API Design")).toBeInTheDocument();
    expect(screen.getByText("Design REST endpoints")).toBeInTheDocument();

    // Step 4: Finalize
    mockFinalizeFlow.mockResolvedValue({
      project_id: "proj-42",
      sessions: [{ id: "s2", name: "API Design", mode: "planning" }],
    });

    await user.click(screen.getByText("Create Project"));

    await waitFor(() => {
      expect(mockFinalizeFlow).toHaveBeenCalledWith("f1");
    });
  });

  it("handles next_questions round before brief", async () => {
    const user = userEvent.setup();

    mockStartFlow.mockResolvedValue({
      flow_id: "f2",
      session_id: "s2",
      first_questions: [
        { id: "q1", text: "Initial question?", category: "goals" },
      ],
    });

    renderPage();
    await user.click(screen.getByText("Brainstorm"));

    await waitFor(() => {
      expect(screen.getByLabelText("Initial question?")).toBeInTheDocument();
    });

    // First respond returns more questions
    mockRespondToFlow.mockResolvedValueOnce({
      next_questions: [
        { id: "q2", text: "Follow-up question?", category: "tech" },
      ],
      brief: null,
    });

    await user.type(screen.getByLabelText("Initial question?"), "My answer");
    await user.click(screen.getByText("Submit Answers"));

    await waitFor(() => {
      expect(screen.getByLabelText("Follow-up question?")).toBeInTheDocument();
    });
    expect(
      screen.queryByLabelText("Initial question?"),
    ).not.toBeInTheDocument();
  });
});
