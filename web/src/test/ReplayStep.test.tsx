import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ReplayStep from "@/components/ReplayStep";
import type { ReplayStep as ReplayStepData } from "@/api/replay";

describe("ReplayStep", () => {
  it("renders a message step using MessageBubble", () => {
    const step: ReplayStepData = {
      index: 0,
      timestamp: "2026-01-01T12:00:00Z",
      step_type: "message",
      data: { role: "user", content: "Hello world" },
    };

    render(<ReplayStep step={step} />);

    const bubble = document.querySelector(".message-bubble");
    expect(bubble).toBeTruthy();
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders a tool_call_start step using ToolCallResult", () => {
    const step: ReplayStepData = {
      index: 1,
      timestamp: "2026-01-01T12:00:01Z",
      step_type: "tool_call_start",
      data: { tool: "edit_file" },
    };

    render(<ReplayStep step={step} />);

    const toolCall = document.querySelector(".tool-call-result");
    expect(toolCall).toBeTruthy();
    expect(screen.getByText("edit_file")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders a tool_call_finish step using ToolCallResult", () => {
    const step: ReplayStepData = {
      index: 2,
      timestamp: "2026-01-01T12:00:02Z",
      step_type: "tool_call_finish",
      data: { tool: "edit_file", output: "File edited" },
    };

    render(<ReplayStep step={step} />);

    const toolCall = document.querySelector(".tool-call-result");
    expect(toolCall).toBeTruthy();
    expect(screen.getByText("File edited")).toBeInTheDocument();
  });

  it("renders a file_change step as a diff view", () => {
    const step: ReplayStepData = {
      index: 3,
      timestamp: "2026-01-01T12:00:03Z",
      step_type: "file_change",
      data: { path: "src/main.py", action: "edit", diff: "+new line" },
    };

    render(<ReplayStep step={step} />);

    expect(screen.getByText("File Change")).toBeInTheDocument();
    expect(screen.getByText("src/main.py")).toBeInTheDocument();
    expect(screen.getByText("+new line")).toBeInTheDocument();
  });

  it("renders unknown step types as formatted JSON", () => {
    const step: ReplayStepData = {
      index: 4,
      timestamp: "2026-01-01T12:00:04Z",
      step_type: "custom_event",
      data: { foo: "bar" },
    };

    render(<ReplayStep step={step} />);

    expect(screen.getByText("custom_event")).toBeInTheDocument();
    const jsonView = document.querySelector(".json-view");
    expect(jsonView).toBeTruthy();
    expect(jsonView!.textContent).toContain('"foo"');
    expect(jsonView!.textContent).toContain('"bar"');
  });
});
