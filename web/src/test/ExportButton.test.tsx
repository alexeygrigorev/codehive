import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ExportButton from "@/components/ExportButton";

// Mock the transcript API
vi.mock("@/api/transcript", () => ({
  downloadTranscript: vi.fn(),
}));

import { downloadTranscript } from "@/api/transcript";

const mockDownloadTranscript = vi.mocked(downloadTranscript);

describe("ExportButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDownloadTranscript.mockResolvedValue(undefined);
  });

  it("renders a button with Export label", () => {
    render(<ExportButton sessionId="s1" sessionName="test" />);
    expect(
      screen.getByRole("button", { name: "Export transcript" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  it("shows dropdown with markdown and JSON options when clicked", async () => {
    const user = userEvent.setup();
    render(<ExportButton sessionId="s1" sessionName="test" />);
    await user.click(
      screen.getByRole("button", { name: "Export transcript" }),
    );
    expect(screen.getByText("Export as Markdown")).toBeInTheDocument();
    expect(screen.getByText("Export as JSON")).toBeInTheDocument();
  });

  it("calls downloadTranscript with format=json when Export as JSON clicked", async () => {
    const user = userEvent.setup();
    render(<ExportButton sessionId="s1" sessionName="test" />);
    await user.click(
      screen.getByRole("button", { name: "Export transcript" }),
    );
    await user.click(screen.getByText("Export as JSON"));
    expect(mockDownloadTranscript).toHaveBeenCalledWith("s1", "json", "test");
  });

  it("calls downloadTranscript with format=markdown when Export as Markdown clicked", async () => {
    const user = userEvent.setup();
    render(<ExportButton sessionId="s1" sessionName="test" />);
    await user.click(
      screen.getByRole("button", { name: "Export transcript" }),
    );
    await user.click(screen.getByText("Export as Markdown"));
    expect(mockDownloadTranscript).toHaveBeenCalledWith(
      "s1",
      "markdown",
      "test",
    );
  });

  it("shows loading state while download is in progress", async () => {
    // Make downloadTranscript hang
    let resolveDownload: () => void;
    mockDownloadTranscript.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDownload = resolve;
        }),
    );

    const user = userEvent.setup();
    render(<ExportButton sessionId="s1" sessionName="test" />);

    await user.click(
      screen.getByRole("button", { name: "Export transcript" }),
    );
    await user.click(screen.getByText("Export as JSON"));

    // Should show loading state
    expect(screen.getByText("Exporting...")).toBeInTheDocument();

    // Resolve the download
    resolveDownload!();
    // Wait for state update
    await vi.waitFor(() => {
      expect(screen.getByText("Export")).toBeInTheDocument();
    });
  });

  it("button is disabled when sessionId is not provided", () => {
    render(<ExportButton />);
    const button = screen.getByRole("button", { name: "Export transcript" });
    expect(button).toBeDisabled();
  });

  it("button is enabled when sessionId is provided", () => {
    render(<ExportButton sessionId="s1" />);
    const button = screen.getByRole("button", { name: "Export transcript" });
    expect(button).not.toBeDisabled();
  });
});
