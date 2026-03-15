import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import ChatInput from "@/components/ChatInput";

describe("ChatInput", () => {
  it("renders a text input and a send button", () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByLabelText("Message input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("calls onSend with input text when send button is clicked", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input");
    await user.type(input, "Hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("calls onSend when Enter is pressed (without Shift)", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input");
    await user.type(input, "Hello");
    await user.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("does NOT call onSend when Shift+Enter is pressed", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("clears input after onSend is called", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input") as HTMLTextAreaElement;
    await user.type(input, "Hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(input.value).toBe("");
  });

  it("does not call onSend when input is empty", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables input and button when disabled prop is true", () => {
    render(<ChatInput onSend={vi.fn()} disabled={true} />);
    expect(screen.getByLabelText("Message input")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});
