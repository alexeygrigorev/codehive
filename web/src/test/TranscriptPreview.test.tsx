import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import TranscriptPreview from "@/components/TranscriptPreview";

describe("TranscriptPreview", () => {
  it('displays the transcript text in an editable textarea with aria-label "Voice transcript"', () => {
    render(
      <TranscriptPreview
        transcript="hello world"
        onSend={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );
    const textarea = screen.getByLabelText("Voice transcript");
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveValue("hello world");
  });

  it("calls onSend with the text when Send is clicked", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(
      <TranscriptPreview
        transcript="hello world"
        onSend={onSend}
        onDiscard={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("hello world");
  });

  it("calls onDiscard and does not call onSend when Discard is clicked", async () => {
    const onSend = vi.fn();
    const onDiscard = vi.fn();
    const user = userEvent.setup();
    render(
      <TranscriptPreview
        transcript="hello world"
        onSend={onSend}
        onDiscard={onDiscard}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Discard" }));
    expect(onDiscard).toHaveBeenCalledOnce();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("allows editing the transcript text before sending", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(
      <TranscriptPreview
        transcript="hello"
        onSend={onSend}
        onDiscard={vi.fn()}
      />,
    );
    const textarea = screen.getByLabelText("Voice transcript");
    await user.clear(textarea);
    await user.type(textarea, "edited text");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("edited text");
  });
});
