import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import MainLayout from "@/layouts/MainLayout";
import MessageBubble from "@/components/MessageBubble";
import ProjectCard from "@/components/ProjectCard";
import DiffViewer from "@/components/DiffViewer";
import type { DiffFile } from "@/utils/parseDiff";

// Mock API calls used by Sidebar and SearchBar to prevent fetch errors
vi.mock("@/api/projects", () => ({
  fetchProjects: vi.fn(() => Promise.resolve([])),
}));
vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn(() => Promise.resolve([])),
}));
vi.mock("@/api/search", () => ({
  searchAll: vi.fn(() => Promise.resolve({ results: [], total: 0, has_more: false })),
}));
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: true,
    isLoading: false,
    authEnabled: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshAccessToken: vi.fn(),
    accessToken: null,
    refreshToken: null,
  }),
}));

function enableDarkMode() {
  document.documentElement.classList.add("dark");
}

describe("Dark mode rendering", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.spyOn(window, "matchMedia").mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(() => false),
    }));
  });

  describe("MainLayout", () => {
    it("has dark background classes when dark class is on html", () => {
      enableDarkMode();
      const { container } = render(
        <MemoryRouter>
          <ThemeProvider>
            <MainLayout />
          </ThemeProvider>
        </MemoryRouter>,
      );
      const outerDiv = container.firstElementChild;
      expect(outerDiv?.className).toContain("dark:bg-gray-900");
    });

    it("has dark header classes", () => {
      enableDarkMode();
      const { container } = render(
        <MemoryRouter>
          <ThemeProvider>
            <MainLayout />
          </ThemeProvider>
        </MemoryRouter>,
      );
      const header = container.querySelector("header");
      expect(header?.className).toContain("dark:bg-gray-800");
      expect(header?.className).toContain("dark:border-gray-700");
    });

    it("includes ThemeToggle in header", () => {
      render(
        <MemoryRouter>
          <ThemeProvider>
            <MainLayout />
          </ThemeProvider>
        </MemoryRouter>,
      );
      expect(screen.getByTestId("theme-toggle")).toBeInTheDocument();
    });
  });

  describe("MessageBubble", () => {
    it("user role has dark: variant classes", () => {
      const { container } = render(
        <MessageBubble role="user" content="Hello" />,
      );
      const bubble = container.querySelector(".message-user");
      expect(bubble?.className).toContain("dark:bg-blue-900");
      expect(bubble?.className).toContain("dark:text-blue-100");
    });

    it("assistant role has dark: variant classes", () => {
      const { container } = render(
        <MessageBubble role="assistant" content="Hi" />,
      );
      const bubble = container.querySelector(".message-assistant");
      expect(bubble?.className).toContain("dark:bg-gray-700");
      expect(bubble?.className).toContain("dark:text-gray-100");
    });

    it("system role has dark: variant classes", () => {
      const { container } = render(
        <MessageBubble role="system" content="System" />,
      );
      const bubble = container.querySelector(".message-system");
      expect(bubble?.className).toContain("dark:bg-yellow-900");
      expect(bubble?.className).toContain("dark:text-yellow-200");
    });

    it("tool role has dark: variant classes", () => {
      const { container } = render(
        <MessageBubble role="tool" content="output" />,
      );
      const bubble = container.querySelector(".message-tool");
      expect(bubble?.className).toContain("dark:bg-gray-950");
      expect(bubble?.className).toContain("dark:text-green-400");
    });
  });

  describe("ProjectCard", () => {
    it("has dark background and border classes", () => {
      const { container } = render(
        <MemoryRouter>
          <ProjectCard
            id="p1"
            name="Test"
            description="Desc"
            archetype={null}
            sessionCount={0}
          />
        </MemoryRouter>,
      );
      const link = container.querySelector("a");
      expect(link?.className).toContain("dark:bg-gray-800");
      expect(link?.className).toContain("dark:border-gray-700");
    });

    it("has dark text classes for name", () => {
      render(
        <MemoryRouter>
          <ProjectCard
            id="p1"
            name="Test"
            description="Desc"
            archetype={null}
            sessionCount={0}
          />
        </MemoryRouter>,
      );
      const heading = screen.getByText("Test");
      expect(heading.className).toContain("dark:text-gray-100");
    });
  });

  describe("DiffViewer", () => {
    const diffFile: DiffFile = {
      path: "test.ts",
      additions: 1,
      deletions: 1,
      hunks: [
        {
          oldStart: 1,
          oldCount: 3,
          newStart: 1,
          newCount: 4,
          lines: [
            { type: "context", content: "unchanged", oldLineNumber: 1, newLineNumber: 1 },
            { type: "deletion", content: "removed", oldLineNumber: 2, newLineNumber: null },
            { type: "addition", content: "added", oldLineNumber: null, newLineNumber: 2 },
            { type: "context", content: "unchanged2", oldLineNumber: 3, newLineNumber: 3 },
          ],
        },
      ],
    };

    it("addition lines have dark-mode color classes", () => {
      const { container } = render(<DiffViewer diffFile={diffFile} />);
      // Find the line with "+"
      const lines = container.querySelectorAll("div.flex");
      const additionLine = Array.from(lines).find((el) =>
        el.textContent?.includes("+added"),
      );
      expect(additionLine?.className).toContain("dark:bg-green-900/30");
      expect(additionLine?.className).toContain("dark:text-green-300");
    });

    it("deletion lines have dark-mode color classes", () => {
      const { container } = render(<DiffViewer diffFile={diffFile} />);
      const lines = container.querySelectorAll("div.flex");
      const deletionLine = Array.from(lines).find((el) =>
        el.textContent?.includes("-removed"),
      );
      expect(deletionLine?.className).toContain("dark:bg-red-900/30");
      expect(deletionLine?.className).toContain("dark:text-red-300");
    });
  });
});

describe("Theme persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.spyOn(window, "matchMedia").mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(() => false),
    }));
  });

  function ThemeReader() {
    const { theme, resolvedTheme, setTheme } = useTheme();
    return (
      <div>
        <span data-testid="theme">{theme}</span>
        <span data-testid="resolved">{resolvedTheme}</span>
        <button onClick={() => setTheme("dark")} data-testid="set-dark">
          Dark
        </button>
        <button onClick={() => setTheme("light")} data-testid="set-light">
          Light
        </button>
      </div>
    );
  }

  it("persists dark theme across re-renders (simulating reload)", () => {
    const { unmount } = render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>,
    );

    // Set to dark
    screen.getByTestId("set-dark").click();
    expect(localStorage.getItem("codehive-theme")).toBe("dark");
    unmount();

    // Re-render (simulating page reload)
    render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(screen.getByTestId("resolved").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("persists light theme across re-renders (simulating reload)", () => {
    const { unmount } = render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>,
    );

    screen.getByTestId("set-light").click();
    expect(localStorage.getItem("codehive-theme")).toBe("light");
    unmount();

    render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(screen.getByTestId("resolved").textContent).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("falls back to system preference when localStorage is cleared", () => {
    localStorage.clear();
    render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("system");
  });
});
