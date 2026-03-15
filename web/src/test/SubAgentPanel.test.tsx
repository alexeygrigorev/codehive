import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import SubAgentPanel from "@/components/sidebar/SubAgentPanel";

describe("SubAgentPanel", () => {
  it("renders a placeholder message", () => {
    render(<SubAgentPanel />);
    expect(
      screen.getByText("Sub-agent view coming soon"),
    ).toBeInTheDocument();
  });
});
