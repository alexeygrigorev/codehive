import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import SessionModeIndicator, {
  SESSION_MODES,
  MODE_STYLES,
} from "@/components/SessionModeIndicator";

describe("SessionModeIndicator", () => {
  it.each(SESSION_MODES)("renders the mode name '%s'", (mode) => {
    render(<SessionModeIndicator mode={mode} />);
    expect(screen.getByText(mode)).toBeInTheDocument();
  });

  it.each(SESSION_MODES)(
    "renders '%s' with its distinct CSS class",
    (mode) => {
      const { container } = render(<SessionModeIndicator mode={mode} />);
      const span = container.querySelector(".mode-indicator");
      const expectedStyle = MODE_STYLES[mode];
      for (const cls of expectedStyle.split(" ")) {
        expect(span).toHaveClass(cls);
      }
    },
  );

  it("each mode has a unique color style", () => {
    const styles = SESSION_MODES.map((m) => MODE_STYLES[m]);
    const unique = new Set(styles);
    expect(unique.size).toBe(SESSION_MODES.length);
  });

  it("renders with default/fallback styling for an unknown mode", () => {
    const { container } = render(<SessionModeIndicator mode="unknown-mode" />);
    const span = container.querySelector(".mode-indicator");
    expect(span).toHaveClass("bg-gray-100");
    expect(span).toHaveClass("text-gray-700");
    expect(screen.getByText("unknown-mode")).toBeInTheDocument();
  });
});
