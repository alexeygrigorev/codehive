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

vi.mock("@/api/githubRepos", () => ({
  fetchGhStatus: vi.fn(),
  fetchGhRepos: vi.fn(),
  cloneRepo: vi.fn(),
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

  it("coming soon flow cards are disabled; From Repository is enabled", async () => {
    const user = userEvent.setup();
    renderPage();

    // Three flow cards should be coming soon
    const comingSoonTitles = ["Brainstorm", "Guided Interview", "From Notes"];
    for (const title of comingSoonTitles) {
      const card = screen.getByText(title).closest("[data-testid]");
      expect(card).toBeTruthy();
      expect(card!.getAttribute("aria-disabled")).toBe("true");
    }

    // From Repository should NOT be aria-disabled
    const repoCard = screen.getByText("From Repository").closest("[data-testid]");
    expect(repoCard).toBeTruthy();
    expect(repoCard!.getAttribute("aria-disabled")).toBeNull();

    // Clicking coming soon cards should not call startFlow
    for (const title of comingSoonTitles) {
      await user.click(screen.getByText(title));
    }

    // Clicking From Repository opens repo picker, does not call startFlow
    await user.click(screen.getByText("From Repository"));

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
