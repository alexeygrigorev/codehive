import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect } from "vitest";
import MobileLayout from "@/layouts/MobileLayout";

function renderMobileLayout(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route element={<MobileLayout />}>
          <Route
            path="/"
            element={<div data-testid="child-content">Dashboard Content</div>}
          />
          <Route
            path="/questions"
            element={<div data-testid="child-content">Questions Content</div>}
          />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("MobileLayout", () => {
  it("renders bottom navigation bar with Dashboard, Approvals, and Questions tabs", () => {
    renderMobileLayout();
    const nav = screen.getByTestId("mobile-nav");
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /approvals/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /questions/i })).toBeInTheDocument();
  });

  it("renders Outlet content (child route)", () => {
    renderMobileLayout("/");
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
  });

  it("does not render a desktop sidebar", () => {
    const { container } = renderMobileLayout();
    // The desktop sidebar has w-64 bg-gray-900
    const sidebar = container.querySelector("aside.w-64.bg-gray-900");
    expect(sidebar).toBeNull();
  });
});
