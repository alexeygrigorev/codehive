import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MessageBubble from "@/components/MessageBubble";

describe("MessageBubble", () => {
  it("renders message content text", () => {
    render(<MessageBubble role="user" content="Hello world" />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders user message with user-specific styling", () => {
    const { container } = render(
      <MessageBubble role="user" content="User msg" />,
    );
    const bubble = container.querySelector(".message-user");
    expect(bubble).toBeInTheDocument();
    expect(bubble).toHaveAttribute("data-role", "user");
  });

  it("renders assistant message with assistant-specific styling", () => {
    const { container } = render(
      <MessageBubble role="assistant" content="Assistant msg" />,
    );
    const bubble = container.querySelector(".message-assistant");
    expect(bubble).toBeInTheDocument();
    expect(bubble).toHaveAttribute("data-role", "assistant");
  });

  it("renders system message with system-specific styling", () => {
    const { container } = render(
      <MessageBubble role="system" content="System msg" />,
    );
    const bubble = container.querySelector(".message-system");
    expect(bubble).toBeInTheDocument();
    expect(bubble).toHaveAttribute("data-role", "system");
  });
});
