import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import ToolCallResult from "@/components/ToolCallResult";

describe("ToolCallResult", () => {
  it("renders tool name with wrench icon", () => {
    const { container } = render(
      <ToolCallResult toolName="read_file" finished={false} />,
    );
    // Tool name in monospace bold
    const nameEl = screen.getByText("read_file");
    expect(nameEl).toBeInTheDocument();
    expect(nameEl.className).toContain("font-mono");
    expect(nameEl.className).toContain("font-bold");
    // Wrench icon present
    expect(container.textContent).toContain("\u{1F527}");
  });

  it("renders structured parameters as key-value pairs", () => {
    render(
      <ToolCallResult
        toolName="read_file"
        input={{ file_path: "/src/app.py", line: 42 }}
        finished={true}
      />,
    );
    expect(screen.getByText("file_path:")).toBeInTheDocument();
    expect(screen.getByText("/src/app.py")).toBeInTheDocument();
    expect(screen.getByText("line:")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders string input as single line (backward compat)", () => {
    render(
      <ToolCallResult
        toolName="read_file"
        input="some raw input string"
        finished={true}
      />,
    );
    expect(screen.getByText(/some raw input string/)).toBeInTheDocument();
  });

  it("shows spinner when not finished", () => {
    const { container } = render(
      <ToolCallResult toolName="read_file" finished={false} />,
    );
    const spinner = container.querySelector(".tool-spinner");
    expect(spinner).toBeInTheDocument();
    expect(spinner?.className).toContain("animate-spin");
    // Also check role for accessibility
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("hides spinner when finished", () => {
    const { container } = render(
      <ToolCallResult toolName="read_file" finished={true} />,
    );
    const spinner = container.querySelector(".tool-spinner");
    expect(spinner).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("result collapsed by default on success", () => {
    const { container } = render(
      <ToolCallResult
        toolName="read_file"
        output="file contents here"
        finished={true}
        isError={false}
      />,
    );
    const details = container.querySelector("details");
    expect(details).toBeInTheDocument();
    // Should NOT have 'open' attribute
    expect(details?.hasAttribute("open")).toBe(false);
  });

  it("result expanded by default on error", () => {
    const { container } = render(
      <ToolCallResult
        toolName="run_command"
        output="command failed"
        finished={true}
        isError={true}
      />,
    );
    const details = container.querySelector("details");
    expect(details).toBeInTheDocument();
    expect(details?.hasAttribute("open")).toBe(true);
  });

  it("user can toggle result visibility", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <ToolCallResult
        toolName="read_file"
        output="file contents here"
        finished={true}
        isError={false}
      />,
    );
    const details = container.querySelector("details") as HTMLDetailsElement;
    const summary = container.querySelector("summary") as HTMLElement;
    expect(details.open).toBe(false);

    // Click to open
    await user.click(summary);
    expect(details.open).toBe(true);

    // Click to close
    await user.click(summary);
    expect(details.open).toBe(false);
  });

  it("shows error badge when isError is true", () => {
    render(
      <ToolCallResult
        toolName="run_command"
        output="failed"
        isError={true}
        finished={true}
      />,
    );
    const badge = screen.getByText("Error");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-red-100");
  });

  it("does not show error badge on success", () => {
    render(
      <ToolCallResult
        toolName="read_file"
        output="ok"
        isError={false}
        finished={true}
      />,
    );
    expect(screen.queryByText("Error")).not.toBeInTheDocument();
  });

  it("has correct border color for in-progress state", () => {
    const { container } = render(
      <ToolCallResult toolName="read_file" finished={false} />,
    );
    const el = container.querySelector(".tool-call-result");
    expect(el?.className).toContain("border-yellow-400");
  });

  it("has correct border color for success state", () => {
    const { container } = render(
      <ToolCallResult toolName="read_file" finished={true} isError={false} />,
    );
    const el = container.querySelector(".tool-call-result");
    expect(el?.className).toContain("border-green-400");
  });

  it("has correct border color for error state", () => {
    const { container } = render(
      <ToolCallResult toolName="run_command" finished={true} isError={true} />,
    );
    const el = container.querySelector(".tool-call-result");
    expect(el?.className).toContain("border-red-400");
  });

  it("long output has scroll container with max-height", () => {
    const longOutput = "line\n".repeat(500);
    const { container } = render(
      <ToolCallResult
        toolName="read_file"
        output={longOutput}
        finished={true}
        isError={true}
      />,
    );
    const pre = container.querySelector("pre.tool-output");
    expect(pre).toBeInTheDocument();
    expect(pre?.className).toContain("max-h-60");
    expect(pre?.className).toContain("overflow-auto");
  });

  it("has data-testid and data-tool attributes", () => {
    const { container } = render(
      <ToolCallResult toolName="edit_file" finished={false} />,
    );
    const el = container.querySelector('[data-testid="tool-call-card"]');
    expect(el).toBeInTheDocument();
    expect(el?.getAttribute("data-tool")).toBe("edit_file");
  });

  it("truncates long parameter values", () => {
    const longVal = "x".repeat(200);
    render(
      <ToolCallResult
        toolName="write_file"
        input={{ content: longVal }}
        finished={true}
      />,
    );
    // Should see truncated value with ellipsis, not full 200 chars
    const paramEl = screen.getByText(/\.\.\.$/);
    expect(paramEl).toBeInTheDocument();
    expect(paramEl.textContent!.length).toBeLessThan(200);
  });

  it("renders nested object values as JSON string", () => {
    render(
      <ToolCallResult
        toolName="edit_file"
        input={{ options: { encoding: "utf-8" } }}
        finished={true}
      />,
    );
    expect(
      screen.getByText('{"encoding":"utf-8"}'),
    ).toBeInTheDocument();
  });

  it("uses dark theme classes for backgrounds", () => {
    const { container } = render(
      <ToolCallResult toolName="read_file" finished={true} isError={false} />,
    );
    const el = container.querySelector(".tool-call-result");
    expect(el?.className).toContain("dark:bg-green-950/40");
  });
});
