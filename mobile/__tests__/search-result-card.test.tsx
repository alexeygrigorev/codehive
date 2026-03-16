import React from "react";
import { render, screen } from "@testing-library/react-native";
import SearchResultCard from "../src/components/SearchResultCard";
import type { SearchResult } from "../src/api/search";

describe("SearchResultCard", () => {
  const baseResult: SearchResult = {
    type: "session",
    id: "s1",
    snippet: "Fix authentication bug",
    score: 0.95,
    created_at: new Date().toISOString(),
    project_id: "p1",
    session_id: "s1",
    project_name: "My Project",
    session_name: "Debug Session",
  };

  it("renders snippet text, type badge, and project name", () => {
    render(<SearchResultCard result={baseResult} onPress={jest.fn()} />);

    expect(screen.getByText("Fix authentication bug")).toBeTruthy();
    expect(screen.getByText("session")).toBeTruthy();
    expect(screen.getByText("My Project / Debug Session")).toBeTruthy();
  });

  it("renders timestamp in a human-readable format", () => {
    const result: SearchResult = {
      ...baseResult,
      created_at: new Date(Date.now() - 3600 * 1000).toISOString(),
    };
    render(<SearchResultCard result={result} onPress={jest.fn()} />);

    expect(screen.getByText("1h ago")).toBeTruthy();
  });

  it("handles missing optional fields without crashing", () => {
    const result: SearchResult = {
      type: "event",
      id: "e1",
      snippet: "Event snippet",
      score: 0.5,
      created_at: new Date().toISOString(),
    };
    render(<SearchResultCard result={result} onPress={jest.fn()} />);

    expect(screen.getByText("Event snippet")).toBeTruthy();
    expect(screen.getByText("event")).toBeTruthy();
    // No project_name or session_name -- should not crash
    expect(screen.queryByTestId("project-name")).toBeNull();
    expect(screen.queryByTestId("session-name")).toBeNull();
  });
});
