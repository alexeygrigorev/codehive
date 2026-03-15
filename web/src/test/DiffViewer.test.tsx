import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import DiffViewer from "@/components/DiffViewer";
import type { DiffFile } from "@/utils/parseDiff";

function makeDiffFile(overrides: Partial<DiffFile> = {}): DiffFile {
  return {
    path: "src/app.py",
    additions: 1,
    deletions: 1,
    hunks: [
      {
        oldStart: 1,
        oldCount: 3,
        newStart: 1,
        newCount: 3,
        lines: [
          { type: "context", content: "import os", oldLineNumber: 1, newLineNumber: 1 },
          { type: "addition", content: "import sys", oldLineNumber: null, newLineNumber: 2 },
          { type: "deletion", content: "old_import", oldLineNumber: 2, newLineNumber: null },
          { type: "context", content: "def main():", oldLineNumber: 3, newLineNumber: 3 },
        ],
      },
    ],
    ...overrides,
  };
}

describe("DiffViewer", () => {
  it("renders addition lines with green styling class", () => {
    const file = makeDiffFile();
    const { container } = render(<DiffViewer diffFile={file} />);

    // Find the line containing "+import sys"
    const additionLines = container.querySelectorAll(".bg-green-50");
    expect(additionLines.length).toBeGreaterThanOrEqual(1);
    expect(additionLines[0].textContent).toContain("import sys");
  });

  it("renders deletion lines with red styling class", () => {
    const file = makeDiffFile();
    const { container } = render(<DiffViewer diffFile={file} />);

    const deletionLines = container.querySelectorAll(".bg-red-50");
    expect(deletionLines.length).toBeGreaterThanOrEqual(1);
    expect(deletionLines[0].textContent).toContain("old_import");
  });

  it("renders 'No changes' message when diff data is empty", () => {
    render(<DiffViewer diffFile={null} />);
    expect(screen.getByText("No changes")).toBeInTheDocument();
  });

  it("renders 'No changes' for a diff file with no hunks", () => {
    const file = makeDiffFile({ hunks: [] });
    render(<DiffViewer diffFile={file} />);
    expect(screen.getByText("No changes")).toBeInTheDocument();
  });
});
