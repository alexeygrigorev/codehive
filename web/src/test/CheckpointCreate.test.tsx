import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import CheckpointCreate from "@/components/CheckpointCreate";

vi.mock("@/api/checkpoints", () => ({
  createCheckpoint: vi.fn(),
}));

import { createCheckpoint } from "@/api/checkpoints";
const mockCreateCheckpoint = vi.mocked(createCheckpoint);

describe("CheckpointCreate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a label input field and a submit button", () => {
    render(<CheckpointCreate sessionId="s1" />);

    expect(screen.getByLabelText("Checkpoint label")).toBeInTheDocument();
    expect(screen.getByText("Create Checkpoint")).toBeInTheDocument();
  });

  it("calls createCheckpoint with the entered label on form submit", async () => {
    const user = userEvent.setup();
    mockCreateCheckpoint.mockResolvedValue({
      id: "cp1",
      session_id: "s1",
      label: "my label",
      git_ref: null,
      created_at: "2026-01-01T00:00:00Z",
    });

    render(<CheckpointCreate sessionId="s1" />);

    await user.type(screen.getByLabelText("Checkpoint label"), "my label");
    await user.click(screen.getByText("Create Checkpoint"));

    expect(mockCreateCheckpoint).toHaveBeenCalledWith("s1", "my label");
  });

  it("calls the onCreated callback after successful creation", async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();
    mockCreateCheckpoint.mockResolvedValue({
      id: "cp1",
      session_id: "s1",
      label: null,
      git_ref: null,
      created_at: "2026-01-01T00:00:00Z",
    });

    render(<CheckpointCreate sessionId="s1" onCreated={onCreated} />);

    await user.click(screen.getByText("Create Checkpoint"));

    await waitForOnCreated(onCreated);
    expect(onCreated).toHaveBeenCalled();
  });
});

function waitForOnCreated(fn: ReturnType<typeof vi.fn>): Promise<void> {
  return new Promise<void>((resolve) => {
    const interval = setInterval(() => {
      if (fn.mock.calls.length > 0) {
        clearInterval(interval);
        resolve();
      }
    }, 10);
    setTimeout(() => {
      clearInterval(interval);
      resolve();
    }, 2000);
  });
}
