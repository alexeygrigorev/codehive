import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AddTaskModal from "@/components/pipeline/AddTaskModal";

vi.mock("@/api/pipeline", () => ({
  addTask: vi.fn(),
}));

import { addTask } from "@/api/pipeline";

const mockAddTask = vi.mocked(addTask);

describe("AddTaskModal", () => {
  const defaultProps = {
    projectId: "proj-1",
    onClose: vi.fn(),
    onTaskAdded: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the modal with title input required", () => {
    render(<AddTaskModal {...defaultProps} />);
    expect(screen.getByText("Add Task to Backlog")).toBeInTheDocument();
    const titleInput = screen.getByTestId(
      "add-task-title-input",
    ) as HTMLInputElement;
    expect(titleInput).toBeRequired();
  });

  it("submits the form with correct payload", async () => {
    mockAddTask.mockResolvedValue({
      issue_id: "i1",
      task_id: "t1",
      pipeline_status: "backlog",
    });

    render(<AddTaskModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId("add-task-title-input"), {
      target: { value: "Fix login timeout" },
    });
    fireEvent.change(screen.getByTestId("add-task-description-input"), {
      target: { value: "Session expires too quickly" },
    });
    fireEvent.click(screen.getByTestId("add-task-submit"));

    await waitFor(() => {
      expect(mockAddTask).toHaveBeenCalledWith({
        project_id: "proj-1",
        title: "Fix login timeout",
        description: "Session expires too quickly",
        acceptance_criteria: undefined,
      });
    });

    expect(defaultProps.onTaskAdded).toHaveBeenCalled();
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it("closes the modal when close button is clicked", () => {
    render(<AddTaskModal {...defaultProps} />);
    fireEvent.click(screen.getByTestId("add-task-close"));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it("shows error on API failure", async () => {
    mockAddTask.mockRejectedValue(new Error("Failed to add task: 500"));

    render(<AddTaskModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId("add-task-title-input"), {
      target: { value: "Some task" },
    });
    fireEvent.click(screen.getByTestId("add-task-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("add-task-error")).toHaveTextContent(
        "Failed to add task: 500",
      );
    });
  });
});
