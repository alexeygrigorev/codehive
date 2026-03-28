import { render, screen, waitFor } from "@testing-library/react";
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
  fetchDefaultDirectory: vi.fn(),
  fetchDirectories: vi.fn(),
}));

vi.mock("@/api/githubRepos", () => ({
  fetchGhStatus: vi.fn(),
  fetchGhRepos: vi.fn(),
  cloneRepo: vi.fn(),
}));

import { startFlow } from "@/api/projectFlow";
import { createProject } from "@/api/projects";
import { fetchDefaultDirectory, fetchDirectories } from "@/api/system";

const mockStartFlow = vi.mocked(startFlow);
const mockCreateProject = vi.mocked(createProject);
const mockFetchDefaultDirectory = vi.mocked(fetchDefaultDirectory);
const mockFetchDirectories = vi.mocked(fetchDirectories);

function renderPage() {
  return render(
    <MemoryRouter>
      <NewProjectPage />
    </MemoryRouter>,
  );
}

describe("NewProjectPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchDefaultDirectory.mockResolvedValue({
      default_directory: "/home/user/codehive/",
    });
    mockFetchDirectories.mockResolvedValue({
      path: "/home/user/codehive",
      parent: "/home/user",
      directories: [],
    });
  });

  it("renders four flow type cards with expected titles", () => {
    renderPage();
    expect(screen.getByText("Brainstorm")).toBeInTheDocument();
    expect(screen.getByText("Guided Interview")).toBeInTheDocument();
    expect(screen.getByText("From Notes")).toBeInTheDocument();
    expect(screen.getByText("From Repository")).toBeInTheDocument();
  });

  describe("Coming soon cards", () => {
    it("three flow cards display a 'Coming soon' badge (From Repository is enabled)", () => {
      renderPage();
      const badges = screen.getAllByText("Coming soon");
      expect(badges).toHaveLength(3);
    });

    it("coming soon cards have opacity-50 and cursor-not-allowed classes", () => {
      renderPage();
      const card = screen.getByTestId("flow-card-brainstorm");
      expect(card.className).toContain("opacity-50");
      expect(card.className).toContain("cursor-not-allowed");
    });

    it("coming soon cards have aria-disabled attribute", () => {
      renderPage();
      const card = screen.getByTestId("flow-card-brainstorm");
      expect(card).toHaveAttribute("aria-disabled", "true");
    });

    it("clicking a coming soon card does NOT call startFlow", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Brainstorm"));
      await user.click(screen.getByText("Guided Interview"));
      await user.click(screen.getByText("From Notes"));

      expect(mockStartFlow).not.toHaveBeenCalled();
    });

    it("clicking From Repository does NOT call startFlow (opens repo picker instead)", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("From Repository"));

      expect(mockStartFlow).not.toHaveBeenCalled();
    });

    it("clicking a coming soon card does not show loading indicator", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Brainstorm"));

      expect(screen.queryByText("Starting flow...")).not.toBeInTheDocument();
    });

    it("clicking a coming soon card does not show error message", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Brainstorm"));

      expect(screen.queryByText(/Failed/)).not.toBeInTheDocument();
    });
  });

  describe("Empty Project form", () => {
    it("clicking Empty Project shows the directory path input and project name input", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));

      expect(screen.getByLabelText(/Directory Path/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Project Name/)).toBeInTheDocument();
      expect(screen.getByText("Create Project")).toBeInTheDocument();
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    it("entering a path auto-derives the project name from basename", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "/home/user/git/myapp");

      const nameInput = screen.getByLabelText(
        /Project Name/,
      ) as HTMLInputElement;
      expect(nameInput.value).toBe("myapp");
    });

    it("submitting with empty path shows 'Directory path is required' error", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.click(screen.getByText("Create Project"));

      expect(
        screen.getByText("Directory path is required"),
      ).toBeInTheDocument();
    });

    it("submitting with relative path shows 'Path must be absolute' error", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "foo/bar");
      await user.click(screen.getByText("Create Project"));

      expect(
        screen.getByText("Path must be absolute (start with /)"),
      ).toBeInTheDocument();
    });

    it("submitting with valid absolute path calls createProject with correct name, path, and git_init", async () => {
      const user = userEvent.setup();
      mockCreateProject.mockResolvedValue({
        id: "p1",
        name: "myapp",
        path: "/home/user/git/myapp",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-03-18T00:00:00Z",
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "/home/user/git/myapp");
      await user.click(screen.getByText("Create Project"));

      await waitFor(() => {
        expect(mockCreateProject).toHaveBeenCalledWith({
          name: "myapp",
          path: "/home/user/git/myapp",
          git_init: true,
        });
      });
    });

    it("clicking Cancel hides the form", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      expect(screen.getByLabelText(/Directory Path/)).toBeInTheDocument();

      await user.click(screen.getByText("Cancel"));
      expect(
        screen.queryByLabelText(/Directory Path/),
      ).not.toBeInTheDocument();
    });

    it("user can manually override the auto-derived name and the override is preserved", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "/home/user/git/myapp");

      const nameInput = screen.getByLabelText(
        /Project Name/,
      ) as HTMLInputElement;
      expect(nameInput.value).toBe("myapp");

      await user.clear(nameInput);
      await user.type(nameInput, "custom-name");

      // Now change the path -- name should NOT update since user edited it
      await user.clear(pathInput);
      await user.type(pathInput, "/home/user/git/other");

      expect(nameInput.value).toBe("custom-name");
    });

    it("error message is displayed when createProject rejects", async () => {
      const user = userEvent.setup();
      mockCreateProject.mockRejectedValue(
        new Error("Failed to create project: 500"),
      );

      renderPage();
      await user.click(screen.getByText("Empty Project"));
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "/home/user/git/myapp");
      await user.click(screen.getByText("Create Project"));

      await waitFor(() => {
        expect(
          screen.getByText("Failed to create project: 500"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Default directory pre-fill", () => {
    it("pre-fills the path field with the default directory when form opens", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        const pathInput = screen.getByLabelText(
          /Directory Path/,
        ) as HTMLInputElement;
        expect(pathInput.value).toBe("/home/user/codehive/");
      });
    });

    it("does not crash if fetchDefaultDirectory fails", async () => {
      mockFetchDefaultDirectory.mockRejectedValue(new Error("network error"));
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));

      // Path should be empty since fetch failed
      const pathInput = screen.getByLabelText(
        /Directory Path/,
      ) as HTMLInputElement;
      expect(pathInput.value).toBe("");
    });
  });

  describe("Git init checkbox", () => {
    it("git init checkbox is present and checked by default", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));

      const checkbox = screen.getByTestId(
        "git-init-checkbox",
      ) as HTMLInputElement;
      expect(checkbox).toBeInTheDocument();
      expect(checkbox.checked).toBe(true);
    });

    it("git init checkbox can be unchecked by user", async () => {
      const user = userEvent.setup();
      mockCreateProject.mockResolvedValue({
        id: "p1",
        name: "myapp",
        path: "/tmp/myapp",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-03-18T00:00:00Z",
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));

      // Type the path first, then uncheck git init
      // (typing in path resets gitInit to true via onChange)
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "/tmp/myapp");

      const checkbox = screen.getByTestId(
        "git-init-checkbox",
      ) as HTMLInputElement;
      await user.click(checkbox);
      expect(checkbox.checked).toBe(false);

      // Submit and verify git_init is false
      await user.click(screen.getByText("Create Project"));

      await waitFor(() => {
        expect(mockCreateProject).toHaveBeenCalledWith(
          expect.objectContaining({ git_init: false }),
        );
      });
    });

    it("selecting a git directory hides the checkbox and shows 'Git repository detected' indicator", async () => {
      const user = userEvent.setup();
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "myrepo",
            path: "/home/user/codehive/myrepo",
            has_git: true,
          },
        ],
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));

      // Wait for browse entries to load
      await waitFor(() => {
        expect(
          screen.getByTestId("browse-entry-myrepo"),
        ).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("browse-entry-myrepo"));

      // Checkbox should NOT be in the DOM
      expect(
        screen.queryByTestId("git-init-checkbox"),
      ).not.toBeInTheDocument();

      // Indicator should be visible
      expect(
        screen.getByTestId("git-detected-indicator"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Git repository detected"),
      ).toBeInTheDocument();
    });

    it("selecting a non-git directory shows the checkbox and no indicator", async () => {
      const user = userEvent.setup();
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "newproj",
            path: "/home/user/codehive/newproj",
            has_git: false,
          },
        ],
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(
          screen.getByTestId("browse-entry-newproj"),
        ).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("browse-entry-newproj"));

      // Checkbox should be present and checked
      const checkbox = screen.getByTestId(
        "git-init-checkbox",
      ) as HTMLInputElement;
      expect(checkbox).toBeInTheDocument();
      expect(checkbox.checked).toBe(true);

      // Indicator should NOT be in the DOM
      expect(
        screen.queryByTestId("git-detected-indicator"),
      ).not.toBeInTheDocument();
    });

    it("switching from git directory to non-git directory: indicator disappears, checkbox reappears", async () => {
      const user = userEvent.setup();
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "gitrepo",
            path: "/home/user/codehive/gitrepo",
            has_git: true,
          },
          {
            name: "plaindir",
            path: "/home/user/codehive/plaindir",
            has_git: false,
          },
        ],
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(
          screen.getByTestId("browse-entry-gitrepo"),
        ).toBeInTheDocument();
      });

      // Select git directory first
      await user.click(screen.getByTestId("browse-entry-gitrepo"));
      expect(
        screen.getByTestId("git-detected-indicator"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("git-init-checkbox"),
      ).not.toBeInTheDocument();

      // Now select non-git directory
      await user.click(screen.getByTestId("browse-entry-plaindir"));
      expect(
        screen.queryByTestId("git-detected-indicator"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("git-init-checkbox")).toBeInTheDocument();
    });

    it("after selecting a git directory, manually typing in path restores the checkbox", async () => {
      const user = userEvent.setup();
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "myrepo",
            path: "/home/user/codehive/myrepo",
            has_git: true,
          },
        ],
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(
          screen.getByTestId("browse-entry-myrepo"),
        ).toBeInTheDocument();
      });

      // Select git directory
      await user.click(screen.getByTestId("browse-entry-myrepo"));
      expect(
        screen.getByTestId("git-detected-indicator"),
      ).toBeInTheDocument();

      // Manually type in path field
      const pathInput = screen.getByLabelText(/Directory Path/);
      await user.clear(pathInput);
      await user.type(pathInput, "/some/other/path");

      // Checkbox should reappear, indicator should disappear
      expect(
        screen.queryByTestId("git-detected-indicator"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("git-init-checkbox")).toBeInTheDocument();
    });

    it("creating a project after selecting a git directory sends git_init: false", async () => {
      const user = userEvent.setup();
      mockCreateProject.mockResolvedValue({
        id: "p1",
        name: "myrepo",
        path: "/home/user/codehive/myrepo",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-03-18T00:00:00Z",
      });
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "myrepo",
            path: "/home/user/codehive/myrepo",
            has_git: true,
          },
        ],
      });

      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(
          screen.getByTestId("browse-entry-myrepo"),
        ).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("browse-entry-myrepo"));
      await user.click(screen.getByText("Create Project"));

      await waitFor(() => {
        expect(mockCreateProject).toHaveBeenCalledWith(
          expect.objectContaining({ git_init: false }),
        );
      });
    });
  });

  describe("Directory browser", () => {
    it("shows browse panel when form is opened", async () => {
      const user = userEvent.setup();
      renderPage();

      await user.click(screen.getByText("Empty Project"));

      expect(screen.getByTestId("browse-panel")).toBeInTheDocument();
    });

    it("browse panel lists subdirectories returned by API", async () => {
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "appA",
            path: "/home/user/codehive/appA",
            has_git: false,
          },
          {
            name: "appB",
            path: "/home/user/codehive/appB",
            has_git: true,
          },
        ],
      });

      const user = userEvent.setup();
      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(screen.getByTestId("browse-entry-appA")).toBeInTheDocument();
        expect(screen.getByTestId("browse-entry-appB")).toBeInTheDocument();
      });

      // appB should have a git badge
      const appBButton = screen.getByTestId("browse-entry-appB");
      expect(appBButton.textContent).toContain("git");
    });

    it("clicking a subdirectory updates the path field", async () => {
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [
          {
            name: "myproj",
            path: "/home/user/codehive/myproj",
            has_git: false,
          },
        ],
      });

      const user = userEvent.setup();
      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(
          screen.getByTestId("browse-entry-myproj"),
        ).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("browse-entry-myproj"));

      const pathInput = screen.getByLabelText(
        /Directory Path/,
      ) as HTMLInputElement;
      expect(pathInput.value).toBe("/home/user/codehive/myproj");
    });

    it("parent (..) entry navigates to parent directory", async () => {
      mockFetchDirectories.mockResolvedValue({
        path: "/home/user/codehive",
        parent: "/home/user",
        directories: [],
      });

      const user = userEvent.setup();
      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(screen.getByTestId("browse-parent")).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("browse-parent"));

      const pathInput = screen.getByLabelText(
        /Directory Path/,
      ) as HTMLInputElement;
      expect(pathInput.value).toBe("/home/user");
    });

    it("shows error message when directory listing fails", async () => {
      mockFetchDirectories.mockRejectedValue(
        new Error("Directory not found"),
      );

      const user = userEvent.setup();
      renderPage();
      await user.click(screen.getByText("Empty Project"));

      await waitFor(() => {
        expect(screen.getByText("Directory not found")).toBeInTheDocument();
      });
    });

    it("browse panel can be toggled closed and open", async () => {
      const user = userEvent.setup();
      renderPage();
      await user.click(screen.getByText("Empty Project"));

      expect(screen.getByTestId("browse-panel")).toBeInTheDocument();

      await user.click(screen.getByTestId("browse-toggle"));
      expect(screen.queryByTestId("browse-panel")).not.toBeInTheDocument();

      await user.click(screen.getByTestId("browse-toggle"));
      expect(screen.getByTestId("browse-panel")).toBeInTheDocument();
    });
  });
});
