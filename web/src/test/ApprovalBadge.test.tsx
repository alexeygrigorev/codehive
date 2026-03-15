import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ApprovalBadge from "@/components/ApprovalBadge";

describe("ApprovalBadge", () => {
  it("renders nothing when count is 0", () => {
    const { container } = render(<ApprovalBadge count={0} />);
    expect(container.querySelector(".approval-badge")).not.toBeInTheDocument();
  });

  it("renders the count number when count > 0", () => {
    render(<ApprovalBadge count={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders with a visually distinct badge style (red background)", () => {
    const { container } = render(<ApprovalBadge count={5} />);
    const badge = container.querySelector(".approval-badge");
    expect(badge).toHaveClass("bg-red-600");
    expect(badge).toHaveClass("text-white");
  });
});
