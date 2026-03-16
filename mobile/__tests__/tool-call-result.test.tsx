import React from "react";
import { render, screen } from "@testing-library/react-native";
import ToolCallResult from "../src/components/ToolCallResult";

describe("ToolCallResult", () => {
  it("renders tool name and result text", () => {
    render(
      <ToolCallResult
        metadata={{ tool_name: "read_file", result: "file contents" }}
      />
    );

    expect(screen.getByText("read_file")).toBeTruthy();
    expect(screen.getByText("file contents")).toBeTruthy();
  });

  it("truncates long result text", () => {
    const longResult = "x".repeat(300);
    render(
      <ToolCallResult metadata={{ tool_name: "bash", result: longResult }} />
    );

    expect(screen.getByText("bash")).toBeTruthy();
    const resultText = screen.getByTestId("tool-result-text");
    // The displayed text should be truncated to 200 chars + "..."
    expect(resultText.props.children.length).toBeLessThan(longResult.length);
    expect(resultText.props.children).toContain("...");
  });
});
