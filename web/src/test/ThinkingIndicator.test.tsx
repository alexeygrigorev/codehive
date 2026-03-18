import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ThinkingIndicator from "@/components/ThinkingIndicator";

describe("ThinkingIndicator", () => {
  it("renders with data-testid", () => {
    render(<ThinkingIndicator />);
    expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument();
  });

  it("renders three dots", () => {
    const { container } = render(<ThinkingIndicator />);
    const dots = container.querySelectorAll("span.animate-bounce");
    expect(dots).toHaveLength(3);
  });

  it("uses assistant-style bubble classes", () => {
    render(<ThinkingIndicator />);
    const el = screen.getByTestId("thinking-indicator");
    expect(el.className).toContain("mr-auto");
    expect(el.className).toContain("bg-gray-100");
    expect(el.className).toContain("rounded-lg");
  });

  it("supports dark mode classes", () => {
    render(<ThinkingIndicator />);
    const el = screen.getByTestId("thinking-indicator");
    expect(el.className).toContain("dark:bg-gray-700");
  });

  it("applies staggered animation delays to dots", () => {
    const { container } = render(<ThinkingIndicator />);
    const dots = container.querySelectorAll("span.animate-bounce");
    const delays = Array.from(dots).map(
      (dot) => (dot as HTMLElement).style.animationDelay,
    );
    expect(delays).toEqual(["0ms", "150ms", "300ms"]);
  });
});
