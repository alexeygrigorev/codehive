import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import DiffFileList from "@/components/DiffFileList";
import type { DiffFileEntry } from "@/api/diffs";

const mockFiles: DiffFileEntry[] = [
  { path: "src/auth.py", diff_text: "...", additions: 5, deletions: 2 },
  { path: "src/main.py", diff_text: "...", additions: 10, deletions: 0 },
];

describe("DiffFileList", () => {
  it("renders file names and line count summaries for each changed file", () => {
    render(<DiffFileList files={mockFiles} onSelectFile={() => {}} />);

    expect(screen.getByText("src/auth.py")).toBeInTheDocument();
    expect(screen.getByText("src/main.py")).toBeInTheDocument();
    expect(screen.getByText("+5")).toBeInTheDocument();
    expect(screen.getByText("-2")).toBeInTheDocument();
    expect(screen.getByText("+10")).toBeInTheDocument();
    expect(screen.getByText("-0")).toBeInTheDocument();
  });

  it("fires a callback when a file entry is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<DiffFileList files={mockFiles} onSelectFile={onSelect} />);

    await user.click(screen.getByText("src/auth.py"));
    expect(onSelect).toHaveBeenCalledWith("src/auth.py");
  });

  it("shows empty state when no files", () => {
    render(<DiffFileList files={[]} onSelectFile={() => {}} />);
    expect(screen.getByText("No changed files")).toBeInTheDocument();
  });
});
