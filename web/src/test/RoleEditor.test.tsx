import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RoleEditor from "@/components/RoleEditor";

vi.mock("@/api/roles", () => ({
  createRole: vi.fn(),
  updateRole: vi.fn(),
}));

import { createRole, updateRole } from "@/api/roles";
const mockCreateRole = vi.mocked(createRole);
const mockUpdateRole = vi.mocked(updateRole);

const mockRole = {
  name: "my-role",
  display_name: "My Role",
  description: "A test role",
  is_builtin: false,
  responsibilities: ["resp1"],
  allowed_tools: ["tool1"],
  denied_tools: ["tool2"],
  coding_rules: ["rule1"],
  system_prompt_extra: "extra prompt",
};

describe("RoleEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all form fields", () => {
    render(<RoleEditor />);

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Display Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Responsibilities (one per line)"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Allowed Tools (one per line)"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Denied Tools (one per line)"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Coding Rules (one per line)"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("System Prompt Extra")).toBeInTheDocument();
  });

  it("calls createRole on submit in create mode", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    mockCreateRole.mockResolvedValue(mockRole);

    render(<RoleEditor onSaved={onSaved} />);

    await user.type(screen.getByLabelText("Name"), "new-role");
    await user.type(screen.getByLabelText("Display Name"), "New Role");
    await user.type(screen.getByLabelText("Description"), "desc");
    await user.click(screen.getByText("Create"));

    expect(mockCreateRole).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "new-role",
        display_name: "New Role",
        description: "desc",
      }),
    );
  });

  it("calls updateRole on submit in edit mode", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    mockUpdateRole.mockResolvedValue(mockRole);

    render(<RoleEditor role={mockRole} onSaved={onSaved} />);

    await user.clear(screen.getByLabelText("Display Name"));
    await user.type(screen.getByLabelText("Display Name"), "Updated Name");
    await user.click(screen.getByText("Update"));

    expect(mockUpdateRole).toHaveBeenCalledWith(
      "my-role",
      expect.objectContaining({
        display_name: "Updated Name",
      }),
    );
  });

  it("disables the name field in edit mode", () => {
    render(<RoleEditor role={mockRole} />);

    expect(screen.getByLabelText("Name")).toBeDisabled();
  });

  it("name field is enabled in create mode", () => {
    render(<RoleEditor />);

    expect(screen.getByLabelText("Name")).not.toBeDisabled();
  });
});
