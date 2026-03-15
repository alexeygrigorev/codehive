import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RoleList from "@/components/RoleList";

vi.mock("@/api/roles", () => ({
  fetchRoles: vi.fn(),
  deleteRole: vi.fn(),
}));

import { fetchRoles, deleteRole } from "@/api/roles";
const mockFetchRoles = vi.mocked(fetchRoles);
const mockDeleteRole = vi.mocked(deleteRole);

const mockRoles = [
  {
    name: "developer",
    display_name: "Developer",
    description: "Writes code",
    is_builtin: true,
    responsibilities: [],
    allowed_tools: [],
    denied_tools: [],
    coding_rules: [],
    system_prompt_extra: "",
  },
  {
    name: "custom-role",
    display_name: "Custom Role",
    description: "A custom role",
    is_builtin: false,
    responsibilities: [],
    allowed_tools: [],
    denied_tools: [],
    coding_rules: [],
    system_prompt_extra: "",
  },
];

describe("RoleList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetch is pending", () => {
    mockFetchRoles.mockReturnValue(new Promise(() => {}));
    render(<RoleList />);
    expect(screen.getByText("Loading roles...")).toBeInTheDocument();
  });

  it("renders all roles with name and description", async () => {
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RoleList />);

    await waitFor(() => {
      expect(screen.getByText("developer")).toBeInTheDocument();
    });
    expect(screen.getByText("Writes code")).toBeInTheDocument();
    expect(screen.getByText("custom-role")).toBeInTheDocument();
    expect(screen.getByText("A custom role")).toBeInTheDocument();
  });

  it("shows Built-in badge for built-in roles and Custom badge for custom roles", async () => {
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RoleList />);

    await waitFor(() => {
      expect(screen.getByText("developer")).toBeInTheDocument();
    });
    expect(screen.getByText("Built-in")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  it("shows edit/delete buttons only for custom roles", async () => {
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RoleList />);

    await waitFor(() => {
      expect(screen.getByText("developer")).toBeInTheDocument();
    });

    // Only one Edit and one Delete button (for custom-role)
    const editButtons = screen.getAllByText("Edit");
    const deleteButtons = screen.getAllByText("Delete");
    expect(editButtons).toHaveLength(1);
    expect(deleteButtons).toHaveLength(1);
  });

  it("calls deleteRole when delete button is clicked on a custom role", async () => {
    const user = userEvent.setup();
    mockFetchRoles.mockResolvedValue(mockRoles);
    mockDeleteRole.mockResolvedValue(undefined);
    render(<RoleList />);

    await waitFor(() => {
      expect(screen.getByText("custom-role")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));

    expect(mockDeleteRole).toHaveBeenCalledWith("custom-role");

    // Role should be removed from list
    await waitFor(() => {
      expect(screen.queryByText("custom-role")).not.toBeInTheDocument();
    });
  });
});
