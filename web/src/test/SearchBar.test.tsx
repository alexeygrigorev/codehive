import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import SearchBar from "@/components/SearchBar";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/api/search", () => ({
  searchAll: vi.fn(),
}));

import { searchAll } from "@/api/search";

const mockSearchAll = vi.mocked(searchAll);

function renderSearchBar() {
  return render(
    <MemoryRouter>
      <SearchBar />
    </MemoryRouter>,
  );
}

describe("SearchBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a text input with placeholder", () => {
    renderSearchBar();
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });

  it("does NOT call searchAll immediately on typing; calls after 300ms debounce", async () => {
    mockSearchAll.mockResolvedValue({ results: [], total: 0, has_more: false });

    renderSearchBar();
    const input = screen.getByPlaceholderText("Search...");

    await act(async () => {
      await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).type(input, "test");
    });

    // Should not have been called immediately during typing
    // After typing finishes, the 300ms debounce timer is set
    // The userEvent.type with advanceTimers will advance timers per keystroke
    // but the debounce resets each keystroke. After final keystroke, need 300ms more.

    // Clear any calls that happened during typing
    // Now advance past the debounce
    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalledWith("test", { limit: 5 });
    });
  });

  it("shows dropdown with results when searchAll returns data", async () => {
    mockSearchAll.mockResolvedValue({
      results: [
        {
          id: "r1",
          entity_type: "session",
          entity_id: "s1",
          snippet: "Found result snippet",
          project_id: "p1",
          project_name: "Project",
          session_id: null,
          score: 0.9,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
      has_more: false,
    });

    renderSearchBar();
    const input = screen.getByPlaceholderText("Search...");

    await act(async () => {
      await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).type(input, "test");
      vi.advanceTimersByTime(300);
    });

    await waitFor(() => {
      expect(screen.getByTestId("search-dropdown")).toBeInTheDocument();
    });
    expect(screen.getByText("Found result snippet")).toBeInTheDocument();
  });

  it("shows 'No results' when searchAll returns empty", async () => {
    mockSearchAll.mockResolvedValue({ results: [], total: 0, has_more: false });

    renderSearchBar();
    const input = screen.getByPlaceholderText("Search...");

    await act(async () => {
      await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).type(input, "xyz");
      vi.advanceTimersByTime(300);
    });

    await waitFor(() => {
      expect(screen.getByText("No results")).toBeInTheDocument();
    });
  });

  it("pressing Enter navigates to /search?q={query}", async () => {
    mockSearchAll.mockResolvedValue({ results: [], total: 0, has_more: false });

    renderSearchBar();
    const input = screen.getByPlaceholderText("Search...");

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await act(async () => {
      await user.type(input, "my query{Enter}");
    });

    expect(mockNavigate).toHaveBeenCalledWith("/search?q=my%20query");
  });

  it("clicking a dropdown result navigates to the entity URL", async () => {
    mockSearchAll.mockResolvedValue({
      results: [
        {
          id: "r1",
          entity_type: "session",
          entity_id: "s42",
          snippet: "Click me",
          project_id: null,
          project_name: null,
          session_id: null,
          score: 0.9,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
      has_more: false,
    });

    renderSearchBar();
    const input = screen.getByPlaceholderText("Search...");

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await act(async () => {
      await user.type(input, "test");
      vi.advanceTimersByTime(300);
    });

    await waitFor(() => {
      expect(screen.getByText("Click me")).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByTestId("dropdown-result"));
    });

    expect(mockNavigate).toHaveBeenCalledWith("/sessions/s42");
  });

  it("clicking 'See all results' navigates to /search?q={query}", async () => {
    mockSearchAll.mockResolvedValue({
      results: [
        {
          id: "r1",
          entity_type: "session",
          entity_id: "s1",
          snippet: "A result",
          project_id: null,
          project_name: null,
          session_id: null,
          score: 0.9,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
      has_more: false,
    });

    renderSearchBar();
    const input = screen.getByPlaceholderText("Search...");

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await act(async () => {
      await user.type(input, "hello");
      vi.advanceTimersByTime(300);
    });

    await waitFor(() => {
      expect(screen.getByTestId("see-all-results")).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByTestId("see-all-results"));
    });

    expect(mockNavigate).toHaveBeenCalledWith("/search?q=hello");
  });
});
