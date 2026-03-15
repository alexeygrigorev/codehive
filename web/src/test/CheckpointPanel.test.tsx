import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import CheckpointPanel from "@/components/sidebar/CheckpointPanel";

vi.mock("@/components/CheckpointList", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="checkpoint-list" data-session-id={sessionId}>
      CheckpointList
    </div>
  ),
}));

describe("CheckpointPanel", () => {
  it("renders CheckpointList with the correct sessionId", () => {
    render(<CheckpointPanel sessionId="s1" />);

    const list = screen.getByTestId("checkpoint-list");
    expect(list).toBeInTheDocument();
    expect(list.getAttribute("data-session-id")).toBe("s1");
  });
});
