import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MobileSessionHeader from "@/components/mobile/MobileSessionHeader";

describe("MobileSessionHeader", () => {
  it("renders session name, status, and mode", () => {
    render(
      <MobileSessionHeader
        name="Fix login bug"
        status="executing"
        mode="execution"
        pendingApprovals={0}
      />,
    );

    expect(screen.getByText("Fix login bug")).toBeInTheDocument();
    expect(screen.getByText("executing")).toBeInTheDocument();
    expect(screen.getByText("execution")).toBeInTheDocument();
  });

  it("truncates long session names without overflow", () => {
    const longName =
      "This is an extremely long session name that should be truncated on a narrow mobile viewport to prevent horizontal overflow";

    render(
      <MobileSessionHeader
        name={longName}
        status="idle"
        mode="brainstorm"
        pendingApprovals={2}
      />,
    );

    const heading = screen.getByRole("heading");
    expect(heading.textContent).toBe(longName);
    // The heading has the truncate class
    expect(heading.className).toContain("truncate");
    // Pending approvals badge is shown
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("does not show approval count when zero", () => {
    render(
      <MobileSessionHeader
        name="Test"
        status="idle"
        mode="planning"
        pendingApprovals={0}
      />,
    );

    // No approval badge rendered
    const badges = screen
      .queryAllByText(/^\d+$/)
      .filter((el) => el.className.includes("bg-red-100"));
    expect(badges.length).toBe(0);
  });
});
