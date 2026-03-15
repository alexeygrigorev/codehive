import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import MobileNav from "@/components/mobile/MobileNav";

function renderNav(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <MobileNav />
    </MemoryRouter>,
  );
}

describe("MobileNav", () => {
  it("renders all tab links with correct href values", () => {
    renderNav();
    const dashboard = screen.getByRole("link", { name: /dashboard/i });
    const sessions = screen.getByRole("link", { name: /sessions/i });
    const approvals = screen.getByRole("link", { name: /approvals/i });
    const questions = screen.getByRole("link", { name: /questions/i });

    expect(dashboard).toHaveAttribute("href", "/");
    expect(sessions).toHaveAttribute("href", "/sessions");
    expect(approvals).toHaveAttribute("href", "/approvals");
    expect(questions).toHaveAttribute("href", "/questions");
  });

  it("highlights the active tab for /questions", () => {
    renderNav("/questions");
    const questions = screen.getByRole("link", { name: /questions/i });
    expect(questions.className).toContain("text-blue-600");

    const dashboard = screen.getByRole("link", { name: /dashboard/i });
    expect(dashboard.className).not.toContain("text-blue-600");
  });

  it("has sufficient touch target height (min 44px)", () => {
    renderNav();
    const links = screen.getAllByRole("link");
    for (const link of links) {
      const minHeight = link.style.minHeight;
      // The component sets minHeight to 48px via inline style
      expect(parseInt(minHeight, 10)).toBeGreaterThanOrEqual(44);
    }
  });
});
