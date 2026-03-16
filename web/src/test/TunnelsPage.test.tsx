import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import TunnelsPage from "@/pages/TunnelsPage";

vi.mock("@/components/TunnelPanel", () => ({
  default: () => <div data-testid="tunnel-panel">TunnelPanel</div>,
}));

describe("TunnelsPage", () => {
  it("renders a heading with text 'Tunnels'", () => {
    render(<TunnelsPage />);
    expect(
      screen.getByRole("heading", { name: /tunnels/i }),
    ).toBeInTheDocument();
  });

  it("renders the TunnelPanel component", () => {
    render(<TunnelsPage />);
    expect(screen.getByTestId("tunnel-panel")).toBeInTheDocument();
  });
});
