import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RolesPage from "@/pages/RolesPage";

vi.mock("@/api/roles", () => ({
  fetchRoles: vi.fn(),
  deleteRole: vi.fn(),
  createRole: vi.fn(),
  updateRole: vi.fn(),
}));

import { fetchRoles } from "@/api/roles";
const mockFetchRoles = vi.mocked(fetchRoles);

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

describe("RolesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders RoleList", async () => {
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RolesPage />);

    await waitFor(() => {
      expect(screen.getByText("developer")).toBeInTheDocument();
    });
    expect(screen.getByText("custom-role")).toBeInTheDocument();
  });

  it("provides navigation to create roles via RoleEditor", async () => {
    const user = userEvent.setup();
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RolesPage />);

    await waitFor(() => {
      expect(screen.getByText("Create Role")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Create Role"));

    // Should show the editor form
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByText("Create")).toBeInTheDocument();
  });

  it("provides navigation to edit roles via RoleEditor", async () => {
    const user = userEvent.setup();
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RolesPage />);

    await waitFor(() => {
      expect(screen.getByText("Edit")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Edit"));

    // Should show the editor form in edit mode
    expect(screen.getByLabelText("Name")).toBeDisabled();
    expect(screen.getByText("Update")).toBeInTheDocument();
  });
});
