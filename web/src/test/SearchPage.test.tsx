import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SearchPage from "@/pages/SearchPage";

vi.mock("@/api/search", () => ({
  searchAll: vi.fn(),
}));

import { searchAll } from "@/api/search";

const mockSearchAll = vi.mocked(searchAll);

function renderSearchPage(query = "test") {
  return render(
    <MemoryRouter initialEntries={[`/search?q=${query}`]}>
      <SearchPage />
    </MemoryRouter>,
  );
}

describe("SearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads q from URL and calls searchAll on mount", async () => {
    mockSearchAll.mockResolvedValue({ results: [], total: 0, has_more: false });

    renderSearchPage("test");

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalledWith("test", {
        type: undefined,
        limit: 20,
        offset: 0,
      });
    });
  });

  it("displays results returned by the mock API", async () => {
    mockSearchAll.mockResolvedValue({
      results: [
        {
          id: "r1",
          entity_type: "session",
          entity_id: "s1",
          snippet: "My session result",
          project_id: "p1",
          project_name: "Project One",
          session_id: null,
          score: 0.9,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
      has_more: false,
    });

    renderSearchPage("test");

    await waitFor(() => {
      expect(screen.getByText(/My session result/)).toBeInTheDocument();
    });
  });

  it("clicking Sessions tab calls searchAll with type session", async () => {
    mockSearchAll.mockResolvedValue({ results: [], total: 0, has_more: false });

    renderSearchPage("test");

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalled();
    });

    mockSearchAll.mockClear();

    const sessionsTab = screen.getByRole("tab", { name: "Sessions" });
    await act(async () => {
      await userEvent.click(sessionsTab);
    });

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalledWith("test", {
        type: "session",
        limit: 20,
        offset: 0,
      });
    });
  });

  it("shows Load more button when has_more is true", async () => {
    mockSearchAll.mockResolvedValueOnce({
      results: [
        {
          id: "r1",
          entity_type: "session",
          entity_id: "s1",
          snippet: "First page",
          project_id: null,
          project_name: null,
          session_id: null,
          score: 0.9,
          created_at: new Date().toISOString(),
        },
      ],
      total: 25,
      has_more: true,
    });

    renderSearchPage("test");

    await waitFor(() => {
      expect(screen.getByTestId("load-more")).toBeInTheDocument();
    });

    // Click load more
    mockSearchAll.mockResolvedValueOnce({
      results: [
        {
          id: "r2",
          entity_type: "message",
          entity_id: "m1",
          snippet: "Second page",
          project_id: null,
          project_name: null,
          session_id: "s1",
          score: 0.8,
          created_at: new Date().toISOString(),
        },
      ],
      total: 25,
      has_more: false,
    });

    await act(async () => {
      await userEvent.click(screen.getByTestId("load-more"));
    });

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalledWith("test", {
        type: undefined,
        limit: 20,
        offset: 20,
      });
    });

    // Both results should be visible
    await waitFor(() => {
      expect(screen.getByText(/First page/)).toBeInTheDocument();
      expect(screen.getByText(/Second page/)).toBeInTheDocument();
    });
  });

  it("shows empty state when no results found", async () => {
    mockSearchAll.mockResolvedValue({ results: [], total: 0, has_more: false });

    renderSearchPage("test");

    await waitFor(() => {
      expect(screen.getByTestId("search-empty")).toBeInTheDocument();
      expect(screen.getByText("No results found")).toBeInTheDocument();
    });
  });

  it("shows loading indicator while API call is pending", () => {
    mockSearchAll.mockReturnValue(new Promise(() => {})); // never resolves

    renderSearchPage("test");

    expect(screen.getByTestId("search-loading")).toBeInTheDocument();
    expect(screen.getByText("Searching...")).toBeInTheDocument();
  });
});
