import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import SearchResult from "@/components/search/SearchResult";
import type { SearchResultItem } from "@/api/search";

function makeResult(overrides: Partial<SearchResultItem> = {}): SearchResultItem {
  return {
    type: "session",
    id: "s1",
    snippet: "Test snippet text",
    score: 0.9,
    created_at: new Date().toISOString(),
    project_id: "p1",
    session_id: null,
    project_name: "My Project",
    session_name: null,
    ...overrides,
  };
}

function renderResult(result: SearchResultItem, query = "test") {
  return render(
    <MemoryRouter>
      <SearchResult result={result} query={query} />
    </MemoryRouter>,
  );
}

describe("SearchResult", () => {
  it("renders type badge text", () => {
    renderResult(makeResult({ type: "session" }));
    expect(screen.getByTestId("type-badge")).toHaveTextContent("Session");
  });

  it("renders message type badge", () => {
    renderResult(makeResult({ type: "message" }));
    expect(screen.getByTestId("type-badge")).toHaveTextContent("Message");
  });

  it("renders issue type badge", () => {
    renderResult(makeResult({ type: "issue" }));
    expect(screen.getByTestId("type-badge")).toHaveTextContent("Issue");
  });

  it("renders snippet text, project name, and timestamp", () => {
    renderResult(
      makeResult({
        snippet: "Some important snippet",
        project_name: "Alpha Project",
      }),
    );
    expect(screen.getByText(/Some important snippet/)).toBeInTheDocument();
    expect(screen.getByText("Alpha Project")).toBeInTheDocument();
    // Timestamp should render (relative time)
    expect(screen.getByText(/just now|ago/)).toBeInTheDocument();
  });

  it("session-type result links to /sessions/{id}", () => {
    renderResult(makeResult({ type: "session", id: "s42" }));
    const link = screen.getByTestId("search-result");
    expect(link).toHaveAttribute("href", "/sessions/s42");
  });

  it("message-type result links to /sessions/{session_id}", () => {
    renderResult(
      makeResult({
        type: "message",
        id: "m1",
        session_id: "s99",
      }),
    );
    const link = screen.getByTestId("search-result");
    expect(link).toHaveAttribute("href", "/sessions/s99");
  });

  it("issue-type result links to /projects/{project_id}", () => {
    renderResult(
      makeResult({ type: "issue", id: "i1", project_id: "p5" }),
    );
    const link = screen.getByTestId("search-result");
    expect(link).toHaveAttribute("href", "/projects/p5");
  });
});
