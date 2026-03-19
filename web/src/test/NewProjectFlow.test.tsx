import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import NewProjectPage from "@/pages/NewProjectPage";

vi.mock("@/api/projectFlow", () => ({
  startFlow: vi.fn(),
  respondToFlow: vi.fn(),
  finalizeFlow: vi.fn(),
}));

vi.mock("@/api/projects", () => ({
  createProject: vi.fn(),
}));

vi.mock("@/api/system", () => ({
  fetchDefaultDirectory: vi.fn().mockResolvedValue({ default_directory: "" }),
  fetchDirectories: vi.fn().mockResolvedValue({ directories: [], parent: null }),
}));

import { startFlow } from "@/api/projectFlow";

const mockStartFlow = vi.mocked(startFlow);

function renderPage() {
  return render(
    <MemoryRouter>
      <NewProjectPage />
    </MemoryRouter>,
  );
}

describe("NewProjectFlow integration - coming soon cards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("all flow cards are marked as coming soon and do not trigger startFlow", async () => {
    const user = userEvent.setup();
    renderPage();

    // All four flow cards should be visible with Coming soon badges
    const flowTitles = ["Brainstorm", "Guided Interview", "From Notes", "From Repository"];
    for (const title of flowTitles) {
      const card = screen.getByText(title).closest("[data-testid]");
      expect(card).toBeTruthy();
      expect(card!.getAttribute("aria-disabled")).toBe("true");
    }

    // Clicking any of them should not call startFlow
    for (const title of flowTitles) {
      await user.click(screen.getByText(title));
    }

    expect(mockStartFlow).not.toHaveBeenCalled();
  });

  it("coming soon cards do not have role=button", () => {
    renderPage();
    const card = screen.getByTestId("flow-card-brainstorm");
    expect(card).not.toHaveAttribute("role", "button");
  });

  it("Empty Project card is not affected by coming soon changes", async () => {
    const user = userEvent.setup();
    renderPage();

    // Empty Project button should still work
    await user.click(screen.getByText("Empty Project"));
    expect(screen.getByLabelText(/Directory Path/)).toBeInTheDocument();
  });
});
