import { render, screen, act, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "@/context/AuthContext";

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

import { loginUser, registerUser, refreshToken, getMe } from "@/api/auth";

const mockLoginUser = vi.mocked(loginUser);
const mockRegisterUser = vi.mocked(registerUser);
const mockRefreshToken = vi.mocked(refreshToken);
const mockGetMe = vi.mocked(getMe);

const mockUser = {
  id: "u1",
  email: "test@example.com",
  username: "testuser",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

const mockTokens = {
  access_token: "acc_token",
  refresh_token: "ref_token",
  token_type: "bearer",
};

function AuthConsumer() {
  const { user, isAuthenticated, isLoading, login, register, logout } =
    useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="username">{user?.username ?? "none"}</span>
      <button onClick={() => login("test@example.com", "pass")}>Login</button>
      <button onClick={() => register("test@example.com", "testuser", "pass")}>
        Register
      </button>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
}

function renderWithAuth() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders children when wrapped in AuthProvider", () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <div>child content</div>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });

  it("returns isAuthenticated: false when no tokens in localStorage", async () => {
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("username")).toHaveTextContent("none");
  });

  it("after calling login() with successful API response, isAuthenticated becomes true and user is populated", async () => {
    mockLoginUser.mockResolvedValue(mockTokens);
    mockGetMe.mockResolvedValue(mockUser);

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    await act(async () => {
      screen.getByText("Login").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("username")).toHaveTextContent("testuser");
    expect(localStorage.getItem("codehive_access_token")).toBe("acc_token");
    expect(localStorage.getItem("codehive_refresh_token")).toBe("ref_token");
  });

  it("after calling register() with successful API response, isAuthenticated becomes true and user is populated", async () => {
    mockRegisterUser.mockResolvedValue(mockTokens);
    mockGetMe.mockResolvedValue(mockUser);

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    await act(async () => {
      screen.getByText("Register").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("username")).toHaveTextContent("testuser");
    expect(localStorage.getItem("codehive_access_token")).toBe("acc_token");
  });

  it("after calling logout(), isAuthenticated becomes false, user is null, and localStorage tokens are cleared", async () => {
    mockLoginUser.mockResolvedValue(mockTokens);
    mockGetMe.mockResolvedValue(mockUser);

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    // Login first
    await act(async () => {
      screen.getByText("Login").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    });

    // Now logout
    await act(async () => {
      screen.getByText("Logout").click();
    });

    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("username")).toHaveTextContent("none");
    expect(localStorage.getItem("codehive_access_token")).toBeNull();
    expect(localStorage.getItem("codehive_refresh_token")).toBeNull();
  });

  it("on mount with valid tokens in localStorage, calls getMe and sets isAuthenticated: true", async () => {
    localStorage.setItem("codehive_access_token", "stored_acc");
    localStorage.setItem("codehive_refresh_token", "stored_ref");
    mockGetMe.mockResolvedValue(mockUser);

    renderWithAuth();

    // Should start loading
    expect(screen.getByTestId("loading")).toHaveTextContent("true");

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("username")).toHaveTextContent("testuser");
    expect(mockGetMe).toHaveBeenCalledWith("stored_acc");
  });

  it("on mount with expired tokens, attempts refresh; if refresh fails, sets isAuthenticated: false", async () => {
    localStorage.setItem("codehive_access_token", "expired_acc");
    localStorage.setItem("codehive_refresh_token", "expired_ref");
    mockGetMe.mockRejectedValue(new Error("Unauthorized"));
    mockRefreshToken.mockRejectedValue(new Error("Refresh failed"));

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(localStorage.getItem("codehive_access_token")).toBeNull();
  });
});
