import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import KanbanBoard from "@/components/pipeline/KanbanBoard";
import type { GroupedTasks } from "@/hooks/usePipelinePolling";
import type { PipelineTask } from "@/api/pipeline";

function makeTask(overrides: Partial<PipelineTask> = {}): PipelineTask {
  return {
    id: "t1",
    session_id: "s1",
    title: "Test task",
    instructions: null,
    status: "pending",
    pipeline_status: "backlog",
    priority: 0,
    depends_on: null,
    mode: "auto",
    created_by: "user",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function emptyGrouped(): GroupedTasks {
  return {
    backlog: [],
    grooming: [],
    groomed: [],
    implementing: [],
    testing: [],
    accepting: [],
    done: [],
  };
}

describe("KanbanBoard", () => {
  it("renders 7 column headers", () => {
    render(<KanbanBoard groupedTasks={emptyGrouped()} />);

    expect(screen.getByText("Backlog")).toBeInTheDocument();
    expect(screen.getByText("Grooming")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Implementing")).toBeInTheDocument();
    expect(screen.getByText("Testing")).toBeInTheDocument();
    expect(screen.getByText("Accepting")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("renders tasks in correct columns", () => {
    const grouped = emptyGrouped();
    grouped.backlog = [
      makeTask({ id: "t1", title: "Backlog task", pipeline_status: "backlog" }),
    ];
    grouped.implementing = [
      makeTask({
        id: "t2",
        title: "Implementing task",
        pipeline_status: "implementing",
      }),
    ];
    grouped.done = [
      makeTask({ id: "t3", title: "Done task", pipeline_status: "done" }),
    ];

    render(<KanbanBoard groupedTasks={grouped} />);

    expect(screen.getByText("Backlog task")).toBeInTheDocument();
    expect(screen.getByText("Implementing task")).toBeInTheDocument();
    expect(screen.getByText("Done task")).toBeInTheDocument();
  });

  it("shows correct count badges", () => {
    const grouped = emptyGrouped();
    grouped.backlog = [
      makeTask({ id: "t1", pipeline_status: "backlog" }),
      makeTask({ id: "t2", pipeline_status: "backlog" }),
    ];
    grouped.implementing = [
      makeTask({ id: "t3", pipeline_status: "implementing" }),
    ];

    render(<KanbanBoard groupedTasks={grouped} />);

    expect(screen.getByTestId("column-count-backlog").textContent).toBe("2");
    expect(
      screen.getByTestId("column-count-implementing").textContent,
    ).toBe("1");
    expect(screen.getByTestId("column-count-grooming").textContent).toBe("0");
    expect(screen.getByTestId("column-count-done").textContent).toBe("0");
  });

  it("renders with empty task list, all columns have count 0", () => {
    render(<KanbanBoard groupedTasks={emptyGrouped()} />);

    expect(screen.getByTestId("column-count-backlog").textContent).toBe("0");
    expect(screen.getByTestId("column-count-grooming").textContent).toBe("0");
    expect(screen.getByTestId("column-count-groomed").textContent).toBe("0");
    expect(
      screen.getByTestId("column-count-implementing").textContent,
    ).toBe("0");
    expect(screen.getByTestId("column-count-testing").textContent).toBe("0");
    expect(screen.getByTestId("column-count-accepting").textContent).toBe("0");
    expect(screen.getByTestId("column-count-done").textContent).toBe("0");
  });
});
