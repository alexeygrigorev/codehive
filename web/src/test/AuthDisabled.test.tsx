import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

// Mock the auth API module -- auth DISABLED
vi.mock("@/api/auth", () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  refreshToken: vi.fn(),
  getMe: vi.fn(),
  fetchAuthConfig: vi.fn().mockResolvedValue({ auth_enabled: false }),
}));

// Mock the client module (setAuthDisabled)
vi.mock("@/api/client", () => ({
  setAuthDisabled: vi.fn(),
}));

import { setAuthDisabled } from "@/api/client";

function AuthConsumer() {
  const { isAuthenticated, isLoading, authEnabled } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="auth-enabled">{String(authEnabled)}</span>
    </div>
  );
}

describe("Auth disabled mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("when fetchAuthConfig returns auth_enabled=false, isAuthenticated is true and authEnabled is false", async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("auth-enabled")).toHaveTextContent("false");
  });

  it("calls setAuthDisabled(true) when auth is disabled", async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });
    expect(setAuthDisabled).toHaveBeenCalledWith(true);
  });

  it("ProtectedRoute renders children when auth is disabled (no redirect to login)", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<div>Dashboard Content</div>} />
            </Route>
            <Route path="/login" element={<div>Login Page</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    });
    expect(screen.queryByText("Login Page")).not.toBeInTheDocument();
  });
});
