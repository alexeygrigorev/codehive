import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import FlowChat from "@/components/project-flow/FlowChat";

vi.mock("@/api/projectFlow", () => ({
  startFlow: vi.fn(),
  respondToFlow: vi.fn(),
  finalizeFlow: vi.fn(),
}));

import { respondToFlow } from "@/api/projectFlow";

const mockRespondToFlow = vi.mocked(respondToFlow);

const defaultQuestions = [
  { id: "q1", text: "What is your goal?", category: "goals" },
  { id: "q2", text: "What tech stack?", category: "tech" },
];

function renderChat(props?: { onBriefReady?: (brief: unknown) => void }) {
  const onBriefReady = props?.onBriefReady ?? vi.fn();
  return render(
    <FlowChat
      flowId="f1"
      questions={defaultQuestions}
      onBriefReady={onBriefReady}
    />,
  );
}

describe("FlowChat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders one input field per question", () => {
    renderChat();
    expect(screen.getByLabelText("What is your goal?")).toBeInTheDocument();
    expect(screen.getByLabelText("What tech stack?")).toBeInTheDocument();
  });

  it("displays question text as label for each input", () => {
    renderChat();
    const labels = screen.getAllByRole("textbox");
    expect(labels).toHaveLength(2);
  });

  it("submit button is disabled when any answer is empty", () => {
    renderChat();
    const submitBtn = screen.getByText("Submit Answers");
    expect(submitBtn).toBeDisabled();
  });

  it("submit button is enabled when all answers are filled", async () => {
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText("What is your goal?"), "Build app");
    await user.type(screen.getByLabelText("What tech stack?"), "React");

    expect(screen.getByText("Submit Answers")).not.toBeDisabled();
  });

  it("clicking submit calls respondToFlow with correct payload", async () => {
    const user = userEvent.setup();
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

    const onBriefReady = vi.fn();
    render(
      <FlowChat
        flowId="f1"
        questions={defaultQuestions}
        onBriefReady={onBriefReady}
      />,
    );

    await user.type(screen.getByLabelText("What is your goal?"), "Build app");
    await user.type(screen.getByLabelText("What tech stack?"), "React");
    await user.click(screen.getByText("Submit Answers"));

    await waitFor(() => {
      expect(mockRespondToFlow).toHaveBeenCalledWith("f1", [
        { question_id: "q1", answer: "Build app" },
        { question_id: "q2", answer: "React" },
      ]);
    });
  });

  it("shows loading state during submit", async () => {
    const user = userEvent.setup();
    mockRespondToFlow.mockReturnValue(new Promise(() => {})); // never resolves

    renderChat();

    await user.type(screen.getByLabelText("What is your goal?"), "Build app");
    await user.type(screen.getByLabelText("What tech stack?"), "React");
    await user.click(screen.getByText("Submit Answers"));

    expect(screen.getByText("Submitting...")).toBeInTheDocument();
  });

  it("when response has next_questions, re-renders with new questions", async () => {
    const user = userEvent.setup();
    mockRespondToFlow.mockResolvedValue({
      next_questions: [
        { id: "q3", text: "What about deployment?", category: "architecture" },
      ],
      brief: null,
    });

    renderChat();

    await user.type(screen.getByLabelText("What is your goal?"), "Build app");
    await user.type(screen.getByLabelText("What tech stack?"), "React");
    await user.click(screen.getByText("Submit Answers"));

    await waitFor(() => {
      expect(
        screen.getByLabelText("What about deployment?"),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByLabelText("What is your goal?"),
    ).not.toBeInTheDocument();
  });

  it("when response has brief, calls onBriefReady callback", async () => {
    const user = userEvent.setup();
    const brief = {
      name: "My Project",
      description: "Desc",
      tech_stack: ["React"],
      architecture: "SPA",
      open_decisions: [],
      suggested_sessions: [],
    };
    mockRespondToFlow.mockResolvedValue({
      next_questions: null,
      brief,
    });

    const onBriefReady = vi.fn();
    render(
      <FlowChat
        flowId="f1"
        questions={defaultQuestions}
        onBriefReady={onBriefReady}
      />,
    );

    await user.type(screen.getByLabelText("What is your goal?"), "Build app");
    await user.type(screen.getByLabelText("What tech stack?"), "React");
    await user.click(screen.getByText("Submit Answers"));

    await waitFor(() => {
      expect(onBriefReady).toHaveBeenCalledWith(brief);
    });
  });

  it("shows error message when respondToFlow rejects", async () => {
    const user = userEvent.setup();
    mockRespondToFlow.mockRejectedValue(
      new Error("Failed to respond to flow: 500"),
    );

    renderChat();

    await user.type(screen.getByLabelText("What is your goal?"), "Build app");
    await user.type(screen.getByLabelText("What tech stack?"), "React");
    await user.click(screen.getByText("Submit Answers"));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to respond to flow: 500"),
      ).toBeInTheDocument();
    });
  });
});
