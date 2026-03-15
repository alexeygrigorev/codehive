import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ToolCallResult from "@/components/ToolCallResult";

describe("ToolCallResult", () => {
  it("renders tool name", () => {
    render(<ToolCallResult toolName="read_file" finished={false} />);
    expect(screen.getByText("read_file")).toBeInTheDocument();
  });

  it("renders Running state for unfinished tool calls", () => {
    render(<ToolCallResult toolName="read_file" finished={false} />);
    expect(screen.getByText("Running...")).toBeInTheDocument();
  });

  it("renders result output for finished tool calls", () => {
    render(
      <ToolCallResult
        toolName="read_file"
        output="file contents here"
        finished={true}
      />,
    );
    expect(screen.getByText("file contents here")).toBeInTheDocument();
    expect(screen.queryByText("Running...")).not.toBeInTheDocument();
  });

  it("renders error styling when is_error is true", () => {
    const { container } = render(
      <ToolCallResult
        toolName="run_command"
        output="command failed"
        isError={true}
        finished={true}
      />,
    );
    expect(screen.getByText("Error")).toBeInTheDocument();
    const el = container.querySelector(".tool-call-result");
    expect(el?.className).toContain("border-red-400");
  });
});
