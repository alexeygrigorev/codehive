import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RegisterPage from "@/pages/RegisterPage";
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

import { registerUser, getMe } from "@/api/auth";

const mockRegisterUser = vi.mocked(registerUser);
const mockGetMe = vi.mocked(getMe);

function renderRegisterPage() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders email, username, password, and confirm-password inputs plus submit button", () => {
    renderRegisterPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /register/i }),
    ).toBeInTheDocument();
  });

  it("renders a link to /login", () => {
    renderRegisterPage();
    const loginLink = screen.getByRole("link", { name: /login/i });
    expect(loginLink).toBeInTheDocument();
    expect(loginLink).toHaveAttribute("href", "/login");
  });

  it("shows validation error when password and confirm-password do not match (no API call)", async () => {
    const user = userEvent.setup();

    renderRegisterPage();

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/username/i), "testuser");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "different");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Passwords do not match",
      );
    });
    expect(mockRegisterUser).not.toHaveBeenCalled();
  });

  it("on submit with successful registration, calls register() and stores tokens", async () => {
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
    mockRegisterUser.mockResolvedValue(tokens);
    mockGetMe.mockResolvedValue(userData);

    renderRegisterPage();

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/username/i), "testuser");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(mockRegisterUser).toHaveBeenCalledWith(
        "test@example.com",
        "testuser",
        "password123",
      );
    });
  });

  it("on submit with failed registration (409 duplicate email), displays error message", async () => {
    const user = userEvent.setup();
    mockRegisterUser.mockRejectedValue(
      new Error("Email already registered"),
    );

    renderRegisterPage();

    await user.type(screen.getByLabelText(/email/i), "dupe@example.com");
    await user.type(screen.getByLabelText(/username/i), "testuser");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    await user.click(screen.getByRole("button", { name: /register/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Email already registered",
      );
    });
  });
});
