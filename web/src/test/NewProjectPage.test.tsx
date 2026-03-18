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

vi.mock("@/api/projects", () => ({
  createProject: vi.fn(),
}));

import { startFlow } from "@/api/projectFlow";
import { createProject } from "@/api/projects";

const mockStartFlow = vi.mocked(startFlow);
const mockCreateProject = vi.mocked(createProject);

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

  describe("Empty Project form", () => {
    it("clicking Empty Project shows the directory path input and project name input", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));

      expect(screen.getByLabelText(/Directory Path/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Project Name/)).toBeInTheDocument();
      expect(screen.getByText("Create Project")).toBeInTheDocument();
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    it("entering a path auto-derives the project name from basename", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.type(pathInput, "/home/user/git/myapp");

      const nameInput = screen.getByLabelText(/Project Name/) as HTMLInputElement;
      expect(nameInput.value).toBe("myapp");
    });

    it("submitting with empty path shows 'Directory path is required' error", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      await user.click(screen.getByText("Create Project"));

      expect(screen.getByText("Directory path is required")).toBeInTheDocument();
    });

    it("submitting with relative path shows 'Path must be absolute' error", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.type(pathInput, "foo/bar");
      await user.click(screen.getByText("Create Project"));

      expect(
        screen.getByText("Path must be absolute (start with /)"),
      ).toBeInTheDocument();
    });

    it("submitting with valid absolute path calls createProject with correct name and path", async () => {
      const user = userEvent.setup();
      mockCreateProject.mockResolvedValue({
        id: "p1",
        name: "myapp",
        path: "/home/user/git/myapp",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-03-18T00:00:00Z",
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.type(pathInput, "/home/user/git/myapp");
      await user.click(screen.getByText("Create Project"));

      await waitFor(() => {
        expect(mockCreateProject).toHaveBeenCalledWith({
          name: "myapp",
          path: "/home/user/git/myapp",
        });
      });
    });

    it("clicking Cancel hides the form", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      expect(screen.getByLabelText(/Directory Path/)).toBeInTheDocument();

      await user.click(screen.getByText("Cancel"));
      expect(screen.queryByLabelText(/Directory Path/)).not.toBeInTheDocument();
    });

    it("user can manually override the auto-derived name and the override is preserved", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.type(pathInput, "/home/user/git/myapp");

      const nameInput = screen.getByLabelText(/Project Name/) as HTMLInputElement;
      expect(nameInput.value).toBe("myapp");

      await user.clear(nameInput);
      await user.type(nameInput, "custom-name");

      // Now change the path -- name should NOT update since user edited it
      await user.clear(pathInput);
      await user.type(pathInput, "/home/user/git/other");

      expect(nameInput.value).toBe("custom-name");
    });

    it("error message is displayed when createProject rejects", async () => {
      const user = userEvent.setup();
      mockCreateProject.mockRejectedValue(
        new Error("Failed to create project: 500"),
      );

      renderPage();
      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.type(pathInput, "/home/user/git/myapp");
      await user.click(screen.getByText("Create Project"));

      await waitFor(() => {
        expect(
          screen.getByText("Failed to create project: 500"),
        ).toBeInTheDocument();
      });
    });
  });
});
