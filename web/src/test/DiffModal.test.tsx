import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import DiffModal from "@/components/DiffModal";
import type { DiffFile } from "@/utils/parseDiff";

const mockDiffFile: DiffFile = {
  path: "src/app.py",
  additions: 1,
  deletions: 0,
  hunks: [
    {
      oldStart: 1,
      oldCount: 1,
      newStart: 1,
      newCount: 2,
      lines: [
        { type: "context", content: "import os", oldLineNumber: 1, newLineNumber: 1 },
        { type: "addition", content: "import sys", oldLineNumber: null, newLineNumber: 2 },
      ],
    },
  ],
};

describe("DiffModal", () => {
  it("opens and renders diff content", () => {
    render(<DiffModal isOpen={true} onClose={() => {}} diffFile={mockDiffFile} />);

    expect(screen.getByTestId("diff-modal-overlay")).toBeInTheDocument();
    // Path appears in both the modal header and the DiffViewer header
    expect(screen.getAllByText("src/app.py").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/import sys/)).toBeInTheDocument();
  });

  it("does not render when isOpen is false", () => {
    render(<DiffModal isOpen={false} onClose={() => {}} diffFile={mockDiffFile} />);
    expect(screen.queryByTestId("diff-modal-overlay")).not.toBeInTheDocument();
  });

  it("closes when close button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<DiffModal isOpen={true} onClose={onClose} diffFile={mockDiffFile} />);

    const closeButton = screen.getByRole("button", { name: /close/i });
    await user.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when Escape key is pressed", () => {
    const onClose = vi.fn();
    render(<DiffModal isOpen={true} onClose={onClose} diffFile={mockDiffFile} />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
