import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ContextProgressBarView } from "@/components/ContextProgressBar";

describe("ContextProgressBarView", () => {
  it("renders with green color when usage is under 50%", () => {
    render(
      <ContextProgressBarView
        usagePercent={30}
        usedTokens={60000}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveAttribute("role", "progressbar");

    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill).not.toBeNull();
    expect(fill.className).toContain("context-bar-green");
    expect(fill.style.width).toBe("30%");
  });

  it("renders with yellow color when usage is between 50-80%", () => {
    render(
      <ContextProgressBarView
        usagePercent={65}
        usedTokens={130000}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill.className).toContain("context-bar-yellow");
    expect(fill.style.width).toBe("65%");
  });

  it("renders with red color when usage is above 80%", () => {
    render(
      <ContextProgressBarView
        usagePercent={90}
        usedTokens={180000}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill.className).toContain("context-bar-red");
    expect(fill.style.width).toBe("90%");
  });

  it("renders with minimal width when usage is 0%", () => {
    render(
      <ContextProgressBarView
        usagePercent={0}
        usedTokens={0}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill.className).toContain("context-bar-green");
    // Minimum visible width is 0.5%
    expect(fill.style.width).toBe("0.5%");
  });

  it("caps width at 100% when usage exceeds 100%", () => {
    render(
      <ContextProgressBarView
        usagePercent={120}
        usedTokens={240000}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill.style.width).toBe("100%");
  });

  it("shows tooltip with correct format", () => {
    render(
      <ContextProgressBarView
        usagePercent={16.2}
        usedTokens={32450}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const title = bar.getAttribute("title");
    expect(title).toContain("32,450");
    expect(title).toContain("200,000");
    expect(title).toContain("tokens");
    expect(title).toContain("16%");
  });

  it("shows estimated label in tooltip when estimated is true", () => {
    render(
      <ContextProgressBarView
        usagePercent={10}
        usedTokens={20000}
        contextWindow={200000}
        estimated={true}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const title = bar.getAttribute("title");
    expect(title).toContain("(estimated)");
  });

  it("does not show estimated label when estimated is false", () => {
    render(
      <ContextProgressBarView
        usagePercent={10}
        usedTokens={20000}
        contextWindow={200000}
        estimated={false}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const title = bar.getAttribute("title");
    expect(title).not.toContain("(estimated)");
  });

  it("boundary: exactly 50% shows yellow", () => {
    render(
      <ContextProgressBarView
        usagePercent={50}
        usedTokens={100000}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill.className).toContain("context-bar-yellow");
  });

  it("boundary: exactly 80% shows red", () => {
    render(
      <ContextProgressBarView
        usagePercent={80}
        usedTokens={160000}
        contextWindow={200000}
      />,
    );

    const bar = screen.getByTestId("context-progress-bar");
    const fill = bar.querySelector(".context-progress-fill") as HTMLElement;
    expect(fill.className).toContain("context-bar-red");
  });
});
