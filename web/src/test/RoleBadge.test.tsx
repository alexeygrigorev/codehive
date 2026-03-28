import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import RoleBadge from "@/components/RoleBadge";

describe("RoleBadge", () => {
  it("renders PM badge with blue classes and correct title", () => {
    render(<RoleBadge role="pm" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge).toHaveTextContent("PM");
    expect(badge).toHaveAttribute("title", "Product Manager");
    expect(badge.className).toContain("bg-blue-100");
    expect(badge.className).toContain("text-blue-800");
    expect(badge.className).toContain("dark:bg-blue-900");
    expect(badge.className).toContain("dark:text-blue-200");
  });

  it("renders SWE badge with green classes and correct title", () => {
    render(<RoleBadge role="swe" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge).toHaveTextContent("SWE");
    expect(badge).toHaveAttribute("title", "Software Engineer");
    expect(badge.className).toContain("bg-green-100");
    expect(badge.className).toContain("text-green-800");
  });

  it("renders QA badge with orange classes and correct title", () => {
    render(<RoleBadge role="qa" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge).toHaveTextContent("QA");
    expect(badge).toHaveAttribute("title", "QA Tester");
    expect(badge.className).toContain("bg-orange-100");
    expect(badge.className).toContain("text-orange-800");
  });

  it("renders OnCall badge with red classes and correct title", () => {
    render(<RoleBadge role="oncall" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge).toHaveTextContent("OnCall");
    expect(badge).toHaveAttribute("title", "On-Call Engineer");
    expect(badge.className).toContain("bg-red-100");
    expect(badge.className).toContain("text-red-800");
  });

  it("returns null when role is null", () => {
    const { container } = render(<RoleBadge role={null} />);
    expect(container.innerHTML).toBe("");
    expect(screen.queryByTestId("role-badge")).not.toBeInTheDocument();
  });

  it("returns null when role is undefined", () => {
    const { container } = render(<RoleBadge role={undefined} />);
    expect(container.innerHTML).toBe("");
    expect(screen.queryByTestId("role-badge")).not.toBeInTheDocument();
  });

  it("renders gray fallback badge for unknown role key", () => {
    render(<RoleBadge role="custom-unknown" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge).toHaveTextContent("custom-unknown");
    expect(badge).toHaveAttribute("title", "custom-unknown");
    expect(badge.className).toContain("bg-gray-100");
    expect(badge.className).toContain("text-gray-800");
  });

  it("applies additional className when provided", () => {
    render(<RoleBadge role="pm" className="ml-2" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge.className).toContain("ml-2");
  });

  it("renders as a span with rounded-full pill styles", () => {
    render(<RoleBadge role="swe" />);
    const badge = screen.getByTestId("role-badge");
    expect(badge.tagName).toBe("SPAN");
    expect(badge.className).toContain("rounded-full");
    expect(badge.className).toContain("px-2");
    expect(badge.className).toContain("py-0.5");
    expect(badge.className).toContain("text-xs");
    expect(badge.className).toContain("font-medium");
  });
});
