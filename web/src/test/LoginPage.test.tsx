import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LoginPage from "@/pages/LoginPage";
import { AuthProvider } from "@/context/AuthContext";

// Mock the auth API module
vi.mock("@/api/auth", () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  refreshToken: vi.fn(),
  getMe: vi.fn(),
  fetchAuthConfig: vi
    .fn()
    .mockResolvedValue({ auth_enabled: true }),
}));

// Mock the client module (setAuthDisabled)
vi.mock("@/api/client", () => ({
  setAuthDisabled: vi.fn(),
}));

import { loginUser, getMe } from "@/api/auth";

const mockLoginUser = vi.mocked(loginUser);
const mockGetMe = vi.mocked(getMe);

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders email input, password input, and login/submit button", () => {
    renderLoginPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /login/i }),
    ).toBeInTheDocument();
  });

  it("renders a link to /register", () => {
    renderLoginPage();
    const registerLink = screen.getByRole("link", { name: /register/i });
    expect(registerLink).toBeInTheDocument();
    expect(registerLink).toHaveAttribute("href", "/register");
  });

  it("on submit with successful login, calls login() and stores tokens", async () => {
    const user = userEvent.setup();
    const tokens = {
      access_token: "acc",
      refresh_token: "ref",
      token_type: "bearer",
    };
    const userData = {
      id: "u1",
      email: "test@example.com",
      username: "testuser",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
    };
    mockLoginUser.mockResolvedValue(tokens);
    mockGetMe.mockResolvedValue(userData);

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(mockLoginUser).toHaveBeenCalledWith(
        "test@example.com",
        "password123",
      );
    });
  });

  it("on submit with failed login (401), displays error message and stays on login page", async () => {
    const user = userEvent.setup();
    mockLoginUser.mockRejectedValue(new Error("Invalid email or password"));

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), "bad@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Invalid email or password",
      );
    });
    // Still on login page
    expect(
      screen.getByRole("button", { name: /login/i }),
    ).toBeInTheDocument();
  });

  it("submit button is disabled while request is in-flight", async () => {
    const user = userEvent.setup();
    let resolveLogin!: (value: { access_token: string; refresh_token: string; token_type: string }) => void;
    mockLoginUser.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = resolve;
      }),
    );

    renderLoginPage();

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /login/i }));

    // Button should be disabled during request
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /logging in/i })).toBeDisabled();
    });

    // Resolve the promise to clean up
    resolveLogin!({
      access_token: "acc",
      refresh_token: "ref",
      token_type: "bearer",
    });
    mockGetMe.mockResolvedValue({
      id: "u1",
      email: "test@example.com",
      username: "testuser",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
    });
  });
});
