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

import { startFlow } from "@/api/projectFlow";

const mockStartFlow = vi.mocked(startFlow);

function renderPage() {
  return render(
    <MemoryRouter>
      <NewProjectPage />
    </MemoryRouter>,
  );
}

describe("NewProjectPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders four flow type cards with expected titles", () => {
    renderPage();
    expect(screen.getByText("Brainstorm")).toBeInTheDocument();
    expect(screen.getByText("Guided Interview")).toBeInTheDocument();
    expect(screen.getByText("From Notes")).toBeInTheDocument();
    expect(screen.getByText("From Repository")).toBeInTheDocument();
  });

  it("clicking Brainstorm calls startFlow with flow_type brainstorm", async () => {
    const user = userEvent.setup();
    mockStartFlow.mockResolvedValue({
      flow_id: "f1",
      session_id: "s1",
      first_questions: [
        { id: "q1", text: "What is your goal?", category: "goals" },
      ],
    });

    renderPage();
    await user.click(screen.getByText("Brainstorm"));

    await waitFor(() => {
      expect(mockStartFlow).toHaveBeenCalledWith(
        expect.objectContaining({ flow_type: "brainstorm" }),
      );
    });
  });

  it("clicking Guided Interview calls startFlow with flow_type interview", async () => {
    const user = userEvent.setup();
    mockStartFlow.mockResolvedValue({
      flow_id: "f1",
      session_id: "s1",
      first_questions: [
        { id: "q1", text: "What is your goal?", category: "goals" },
      ],
    });

    renderPage();
    await user.click(screen.getByText("Guided Interview"));

    await waitFor(() => {
      expect(mockStartFlow).toHaveBeenCalledWith(
        expect.objectContaining({ flow_type: "interview" }),
      );
    });
  });

  it("shows loading indicator while startFlow is pending", async () => {
    const user = userEvent.setup();
    mockStartFlow.mockReturnValue(new Promise(() => {})); // never resolves

    renderPage();
    await user.click(screen.getByText("Brainstorm"));

    expect(screen.getByText("Starting flow...")).toBeInTheDocument();
  });

  it("shows error message when startFlow rejects", async () => {
    const user = userEvent.setup();
    mockStartFlow.mockRejectedValue(new Error("Failed to start flow: 500"));

    renderPage();
    await user.click(screen.getByText("Brainstorm"));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to start flow: 500"),
      ).toBeInTheDocument();
    });
  });

  it("transitions to FlowChat after successful startFlow", async () => {
    const user = userEvent.setup();
    mockStartFlow.mockResolvedValue({
      flow_id: "f1",
      session_id: "s1",
      first_questions: [
        { id: "q1", text: "What is your goal?", category: "goals" },
      ],
    });

    renderPage();
    await user.click(screen.getByText("Brainstorm"));

    await waitFor(() => {
      expect(screen.getByText("What is your goal?")).toBeInTheDocument();
    });
    expect(screen.getByText("Submit Answers")).toBeInTheDocument();
  });
});
