import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import SearchHighlight from "@/components/search/SearchHighlight";

describe("SearchHighlight", () => {
  it("wraps matched query term in <mark> tags", () => {
    const { container } = render(
      <SearchHighlight text="user authentication flow" query="auth" />,
    );
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("auth");
    expect(container.textContent).toBe("user authentication flow");
  });

  it("is case-insensitive: query AUTH highlights auth", () => {
    const { container } = render(
      <SearchHighlight text="user authentication flow" query="AUTH" />,
    );
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("auth");
  });

  it("renders text without <mark> when there is no match", () => {
    const { container } = render(
      <SearchHighlight text="hello world" query="xyz" />,
    );
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(0);
    expect(container.textContent).toBe("hello world");
  });

  it("highlights multiple occurrences", () => {
    const { container } = render(
      <SearchHighlight text="test the test case for testing" query="test" />,
    );
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(3);
    marks.forEach((mark) => {
      expect(mark.textContent?.toLowerCase()).toBe("test");
    });
  });

  it("renders plain text when query is empty", () => {
    const { container } = render(
      <SearchHighlight text="some text" query="" />,
    );
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(0);
    expect(container.textContent).toBe("some text");
  });
});
