import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import UserMenu from "@/components/UserMenu";

const mockLogout = vi.fn();

// Mock the AuthContext
vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "@/context/AuthContext";

const mockUseAuth = vi.mocked(useAuth);

describe("UserMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the logged-in user's username", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "u1",
        email: "test@example.com",
        username: "testuser",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      accessToken: "token",
      refreshToken: "ref",
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: mockLogout,
      refreshAccessToken: vi.fn(),
    });

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    );

    expect(screen.getByText("testuser")).toBeInTheDocument();
  });

  it("renders a logout button when dropdown is open", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      user: {
        id: "u1",
        email: "test@example.com",
        username: "testuser",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      accessToken: "token",
      refreshToken: "ref",
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: mockLogout,
      refreshAccessToken: vi.fn(),
    });

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    );

    // Open the dropdown
    await user.click(screen.getByLabelText("User menu"));

    expect(screen.getByText("Logout")).toBeInTheDocument();
  });

  it("clicking logout calls the logout() function from AuthContext", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      user: {
        id: "u1",
        email: "test@example.com",
        username: "testuser",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      accessToken: "token",
      refreshToken: "ref",
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: mockLogout,
      refreshAccessToken: vi.fn(),
    });

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    );

    // Open dropdown and click logout
    await user.click(screen.getByLabelText("User menu"));
    await user.click(screen.getByText("Logout"));

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when user is null", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshAccessToken: vi.fn(),
    });

    const { container } = render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    );

    expect(container.innerHTML).toBe("");
  });
});
