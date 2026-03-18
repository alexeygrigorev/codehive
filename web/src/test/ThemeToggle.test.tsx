import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import ThemeToggle from "@/components/ThemeToggle";

// Helper to read the current theme
function ThemeReader() {
  const { theme } = useTheme();
  return <span data-testid="current-theme">{theme}</span>;
}

function renderToggle() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
      <ThemeReader />
    </ThemeProvider>,
  );
}

describe("ThemeToggle", () => {
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

  it("renders a toggle button", () => {
    renderToggle();
    expect(screen.getByTestId("theme-toggle")).toBeInTheDocument();
  });

  it("displays the appropriate label for the current theme state", () => {
    renderToggle();
    // Default is "system", which shows "Auto"
    expect(screen.getByTestId("theme-toggle").textContent).toBe("Auto");
  });

  it("clicking cycles through light, dark, system", () => {
    renderToggle();
    const button = screen.getByTestId("theme-toggle");

    // Start: system (Auto)
    expect(screen.getByTestId("current-theme").textContent).toBe("system");

    // Click 1: system -> light
    act(() => {
      button.click();
    });
    expect(screen.getByTestId("current-theme").textContent).toBe("light");
    expect(button.textContent).toBe("Sun");

    // Click 2: light -> dark
    act(() => {
      button.click();
    });
    expect(screen.getByTestId("current-theme").textContent).toBe("dark");
    expect(button.textContent).toBe("Moon");

    // Click 3: dark -> system
    act(() => {
      button.click();
    });
    expect(screen.getByTestId("current-theme").textContent).toBe("system");
    expect(button.textContent).toBe("Auto");
  });
});
