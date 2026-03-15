import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RoleAssigner from "@/components/RoleAssigner";

vi.mock("@/api/roles", () => ({
  fetchRoles: vi.fn(),
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
    name: "reviewer",
    display_name: "Reviewer",
    description: "Reviews code",
    is_builtin: false,
    responsibilities: [],
    allowed_tools: [],
    denied_tools: [],
    coding_rules: [],
    system_prompt_extra: "",
  },
];

describe("RoleAssigner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a select element populated with role names", async () => {
    mockFetchRoles.mockResolvedValue(mockRoles);
    render(<RoleAssigner />);

    await waitFor(() => {
      expect(screen.getByLabelText("Select role")).toBeInTheDocument();
    });

    const select = screen.getByLabelText("Select role") as HTMLSelectElement;
    // Default option + 2 roles
    expect(select.options).toHaveLength(3);
    expect(select.options[1].value).toBe("developer");
    expect(select.options[1].text).toBe("Developer");
    expect(select.options[2].value).toBe("reviewer");
    expect(select.options[2].text).toBe("Reviewer");
  });

  it("calls onChange callback with selected role name", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    mockFetchRoles.mockResolvedValue(mockRoles);

    render(<RoleAssigner onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Select role")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Select role"), "developer");

    expect(onChange).toHaveBeenCalledWith("developer");
  });
});
