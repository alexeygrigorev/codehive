import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import BriefReview from "@/components/project-flow/BriefReview";

vi.mock("@/api/projectFlow", () => ({
  startFlow: vi.fn(),
  respondToFlow: vi.fn(),
  finalizeFlow: vi.fn(),
}));

import { finalizeFlow } from "@/api/projectFlow";

const mockFinalizeFlow = vi.mocked(finalizeFlow);

const defaultBrief = {
  name: "My Project",
  description: "A great project",
  tech_stack: ["React", "TypeScript", "Node.js"],
  architecture: "Monorepo with frontend and backend",
  open_decisions: ["Database choice", "Hosting provider"],
  suggested_sessions: [
    { name: "Setup", mission: "Initialize the project", mode: "execution" },
    {
      name: "Backend API",
      mission: "Build the REST API",
      mode: "execution",
    },
  ],
};

function renderBriefReview(
  props?: { onFinalized?: (id: string) => void },
) {
  const onFinalized = props?.onFinalized ?? vi.fn();
  return render(
    <BriefReview
      flowId="f1"
      brief={defaultBrief}
      onFinalized={onFinalized}
    />,
  );
}

describe("BriefReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders project name in an editable input field", () => {
    renderBriefReview();
    const nameInput = screen.getByLabelText("Project Name");
    expect(nameInput).toHaveValue("My Project");
  });

  it("renders project description in an editable textarea", () => {
    renderBriefReview();
    const descInput = screen.getByLabelText("Description");
    expect(descInput).toHaveValue("A great project");
  });

  it("renders tech stack entries", () => {
    renderBriefReview();
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("TypeScript")).toBeInTheDocument();
    expect(screen.getByText("Node.js")).toBeInTheDocument();
  });

  it("renders each suggested session name, mission, and mode", () => {
    renderBriefReview();
    expect(screen.getByText("Setup")).toBeInTheDocument();
    expect(
      screen.getByText("Initialize the project"),
    ).toBeInTheDocument();
    expect(screen.getByText("Backend API")).toBeInTheDocument();
    expect(screen.getByText("Build the REST API")).toBeInTheDocument();
    expect(screen.getAllByText(/Mode: execution/)).toHaveLength(2);
  });

  it("renders open decisions list", () => {
    renderBriefReview();
    expect(screen.getByText("Database choice")).toBeInTheDocument();
    expect(screen.getByText("Hosting provider")).toBeInTheDocument();
  });

  it("editing name updates the displayed value", async () => {
    const user = userEvent.setup();
    renderBriefReview();
    const nameInput = screen.getByLabelText("Project Name");

    await user.clear(nameInput);
    await user.type(nameInput, "New Name");
    expect(nameInput).toHaveValue("New Name");
  });

  it("clicking Create Project calls finalizeFlow with flow_id", async () => {
    const user = userEvent.setup();
    mockFinalizeFlow.mockResolvedValue({
      project_id: "proj-1",
      sessions: [],
    });

    const onFinalized = vi.fn();
    render(
      <BriefReview
        flowId="f1"
        brief={defaultBrief}
        onFinalized={onFinalized}
      />,
    );

    await user.click(screen.getByText("Create Project"));

    await waitFor(() => {
      expect(mockFinalizeFlow).toHaveBeenCalledWith("f1");
    });
  });

  it("shows loading state during finalization", async () => {
    const user = userEvent.setup();
    mockFinalizeFlow.mockReturnValue(new Promise(() => {})); // never resolves

    renderBriefReview();
    await user.click(screen.getByText("Create Project"));

    expect(screen.getByText("Creating...")).toBeInTheDocument();
  });

  it("shows error message when finalizeFlow rejects", async () => {
    const user = userEvent.setup();
    mockFinalizeFlow.mockRejectedValue(
      new Error("Failed to finalize flow: 422"),
    );

    renderBriefReview();
    await user.click(screen.getByText("Create Project"));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to finalize flow: 422"),
      ).toBeInTheDocument();
    });
  });

  it("calls onFinalized with project_id after successful finalization", async () => {
    const user = userEvent.setup();
    mockFinalizeFlow.mockResolvedValue({
      project_id: "proj-1",
      sessions: [{ id: "s1", name: "Setup", mode: "execution" }],
    });

    const onFinalized = vi.fn();
    render(
      <BriefReview
        flowId="f1"
        brief={defaultBrief}
        onFinalized={onFinalized}
      />,
    );

    await user.click(screen.getByText("Create Project"));

    await waitFor(() => {
      expect(onFinalized).toHaveBeenCalledWith("proj-1");
    });
  });
});
