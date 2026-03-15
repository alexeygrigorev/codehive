import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import TunnelPanel from "@/components/TunnelPanel";

vi.mock("@/api/tunnels", () => ({
  fetchTunnels: vi.fn(),
  createTunnel: vi.fn(),
  closeTunnel: vi.fn(),
}));

import { fetchTunnels, createTunnel, closeTunnel } from "@/api/tunnels";
const mockFetchTunnels = vi.mocked(fetchTunnels);
const mockCreateTunnel = vi.mocked(createTunnel);
const mockCloseTunnel = vi.mocked(closeTunnel);

const mockTunnels = [
  {
    id: "t1",
    target_id: "target-abc",
    remote_port: 8080,
    local_port: 3000,
    label: "dev-server",
    status: "active",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "t2",
    target_id: "target-def",
    remote_port: 5432,
    local_port: 5433,
    label: "",
    status: "disconnected",
    created_at: "2026-01-01T01:00:00Z",
  },
];

describe("TunnelPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetch is pending", () => {
    mockFetchTunnels.mockReturnValue(new Promise(() => {}));
    render(<TunnelPanel />);
    expect(screen.getByText("Loading tunnels...")).toBeInTheDocument();
  });

  it("shows empty state when no tunnels returned", async () => {
    mockFetchTunnels.mockResolvedValue([]);
    render(<TunnelPanel />);

    await waitFor(() => {
      expect(screen.getByText("No active tunnels")).toBeInTheDocument();
    });
  });

  it("renders tunnel data with label, ports, status, and preview link", async () => {
    mockFetchTunnels.mockResolvedValue(mockTunnels);
    render(<TunnelPanel />);

    await waitFor(() => {
      expect(screen.getByText("dev-server")).toBeInTheDocument();
    });

    // Check ports
    expect(screen.getByText("8080")).toBeInTheDocument();
    expect(screen.getByText("3000")).toBeInTheDocument();

    // Check status
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("disconnected")).toBeInTheDocument();

    // Check preview links
    const links = screen.getAllByText("Open");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "http://localhost:3000");
    expect(links[1]).toHaveAttribute("href", "http://localhost:5433");
  });

  it("has create-tunnel form with target, port, and label fields", async () => {
    mockFetchTunnels.mockResolvedValue([]);
    render(<TunnelPanel />);

    await waitFor(() => {
      expect(screen.getByText("No active tunnels")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("Target ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Remote Port")).toBeInTheDocument();
    expect(screen.getByLabelText("Local Port")).toBeInTheDocument();
    expect(screen.getByLabelText("Label")).toBeInTheDocument();
    expect(screen.getByText("Create Tunnel")).toBeInTheDocument();
  });

  it("calls createTunnel on form submit", async () => {
    const user = userEvent.setup();
    mockFetchTunnels.mockResolvedValue([]);
    mockCreateTunnel.mockResolvedValue(mockTunnels[0]);

    render(<TunnelPanel />);

    await waitFor(() => {
      expect(screen.getByText("No active tunnels")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Target ID"), "target-abc");
    await user.type(screen.getByLabelText("Remote Port"), "8080");
    await user.type(screen.getByLabelText("Local Port"), "3000");
    await user.type(screen.getByLabelText("Label"), "dev-server");

    await user.click(screen.getByText("Create Tunnel"));

    expect(mockCreateTunnel).toHaveBeenCalledWith({
      target_id: "target-abc",
      remote_port: 8080,
      local_port: 3000,
      label: "dev-server",
    });
  });

  it("renders close button per tunnel", async () => {
    mockFetchTunnels.mockResolvedValue(mockTunnels);
    render(<TunnelPanel />);

    await waitFor(() => {
      expect(screen.getByText("dev-server")).toBeInTheDocument();
    });

    const closeButtons = screen.getAllByText("Close");
    expect(closeButtons).toHaveLength(2);
  });

  it("calls closeTunnel when close button is clicked", async () => {
    const user = userEvent.setup();
    mockFetchTunnels.mockResolvedValue(mockTunnels);
    mockCloseTunnel.mockResolvedValue(undefined);

    render(<TunnelPanel />);

    await waitFor(() => {
      expect(screen.getByText("dev-server")).toBeInTheDocument();
    });

    const closeButtons = screen.getAllByText("Close");
    await user.click(closeButtons[0]);

    expect(mockCloseTunnel).toHaveBeenCalledWith("t1");
  });

  it("shows error state when fetch fails", async () => {
    mockFetchTunnels.mockRejectedValue(
      new Error("Failed to fetch tunnels: 500"),
    );
    render(<TunnelPanel />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch tunnels: 500"),
      ).toBeInTheDocument();
    });
  });
});
