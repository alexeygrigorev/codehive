import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ContextFilesSection from "@/components/ContextFilesSection";

// Mock the API module
vi.mock("@/api/contextFiles", () => ({
  fetchContextFiles: vi.fn(),
  fetchContextFileContent: vi.fn(),
}));

import {
  fetchContextFiles,
  fetchContextFileContent,
} from "@/api/contextFiles";

const mockFetchContextFiles = vi.mocked(fetchContextFiles);
const mockFetchContextFileContent = vi.mocked(fetchContextFileContent);

describe("ContextFilesSection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders file list when files are returned", async () => {
    mockFetchContextFiles.mockResolvedValue([
      { path: "CLAUDE.md", size: 100 },
      { path: ".cursorrules", size: 50 },
    ]);

    render(<ContextFilesSection projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByText("CLAUDE.md")).toBeInTheDocument();
    });
    expect(screen.getByText(".cursorrules")).toBeInTheDocument();
    expect(screen.getByTestId("context-file-list")).toBeInTheDocument();
  });

  it("shows 'No context files detected' when API returns empty list", async () => {
    mockFetchContextFiles.mockResolvedValue([]);

    render(<ContextFilesSection projectId="p1" />);

    await waitFor(() => {
      expect(
        screen.getByText("No context files detected"),
      ).toBeInTheDocument();
    });
  });

  it("shows file content when a file is clicked", async () => {
    mockFetchContextFiles.mockResolvedValue([
      { path: "CLAUDE.md", size: 100 },
    ]);
    mockFetchContextFileContent.mockResolvedValue({
      path: "CLAUDE.md",
      content: "# My Context File",
    });

    render(<ContextFilesSection projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByText("CLAUDE.md")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("CLAUDE.md"));

    await waitFor(() => {
      expect(screen.getByText("# My Context File")).toBeInTheDocument();
    });
    expect(screen.getByTestId("context-file-preview")).toBeInTheDocument();
  });

  it("hides preview when clicking the same file again", async () => {
    mockFetchContextFiles.mockResolvedValue([
      { path: "CLAUDE.md", size: 100 },
    ]);
    mockFetchContextFileContent.mockResolvedValue({
      path: "CLAUDE.md",
      content: "# Content",
    });

    render(<ContextFilesSection projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByText("CLAUDE.md")).toBeInTheDocument();
    });

    // Click to open
    fireEvent.click(screen.getByText("CLAUDE.md"));
    await waitFor(() => {
      expect(screen.getByTestId("context-file-preview")).toBeInTheDocument();
    });

    // Click again to close
    fireEvent.click(screen.getByText("CLAUDE.md"));
    await waitFor(() => {
      expect(
        screen.queryByTestId("context-file-preview"),
      ).not.toBeInTheDocument();
    });
  });
});
