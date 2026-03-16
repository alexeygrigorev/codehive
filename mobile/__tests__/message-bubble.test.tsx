import React from "react";
import { render, screen } from "@testing-library/react-native";
import MessageBubble from "../src/components/MessageBubble";

describe("MessageBubble", () => {
  it("renders user message right-aligned with blue background", () => {
    render(
      <MessageBubble
        message={{
          id: "m1",
          role: "user",
          content: "Hello world",
          created_at: new Date().toISOString(),
        }}
      />
    );

    expect(screen.getByText("Hello world")).toBeTruthy();
    expect(screen.getByTestId("message-bubble-user")).toBeTruthy();
  });

  it("renders assistant message left-aligned with gray background", () => {
    render(
      <MessageBubble
        message={{
          id: "m2",
          role: "assistant",
          content: "I can help with that",
          created_at: new Date().toISOString(),
        }}
      />
    );

    expect(screen.getByText("I can help with that")).toBeTruthy();
    expect(screen.getByTestId("message-bubble-assistant")).toBeTruthy();
  });

  it("renders system message centered with italic/muted text", () => {
    render(
      <MessageBubble
        message={{
          id: "m3",
          role: "system",
          content: "Session started",
          created_at: new Date().toISOString(),
        }}
      />
    );

    expect(screen.getByText("Session started")).toBeTruthy();
    expect(screen.getByTestId("message-bubble-system")).toBeTruthy();
  });

  it("renders tool message with ToolCallResult sub-component", () => {
    render(
      <MessageBubble
        message={{
          id: "m4",
          role: "tool",
          content: "file contents here",
          metadata: { tool_name: "read_file" },
          created_at: new Date().toISOString(),
        }}
      />
    );

    expect(screen.getByTestId("message-bubble-tool")).toBeTruthy();
    expect(screen.getByTestId("tool-call-result")).toBeTruthy();
    expect(screen.getByText("read_file")).toBeTruthy();
  });
});
