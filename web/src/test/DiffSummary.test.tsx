import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import DiffSummary from "@/components/mobile/DiffSummary";
import type { DiffSummaryFile } from "@/components/mobile/DiffSummary";

describe("DiffSummary", () => {
  it("shows correct counts for files, additions, and deletions", () => {
    const files: DiffSummaryFile[] = [
      { path: "src/app.ts", additions: 20, deletions: 5 },
      { path: "src/utils.ts", additions: 15, deletions: 10 },
      { path: "src/index.ts", additions: 15, deletions: 5 },
    ];

    render(<DiffSummary files={files} />);

    expect(screen.getByText("3 files changed")).toBeInTheDocument();
    expect(screen.getByText("+50")).toBeInTheDocument();
    expect(screen.getByText("-20")).toBeInTheDocument();
  });

  it("calls onFileClick when a file name is clicked", async () => {
    const onFileClick = vi.fn();
    const files: DiffSummaryFile[] = [
      { path: "src/main.ts", additions: 10, deletions: 2 },
    ];

    render(<DiffSummary files={files} onFileClick={onFileClick} />);

    const user = userEvent.setup();
    await user.click(screen.getByText("src/main.ts"));

    expect(onFileClick).toHaveBeenCalledWith("src/main.ts");
  });

  it("shows empty state when no files", () => {
    render(<DiffSummary files={[]} />);

    expect(screen.getByText("No changes")).toBeInTheDocument();
  });
});
