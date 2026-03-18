import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ProtectedRoute from "@/components/ProtectedRoute";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import MainLayout from "@/layouts/MainLayout";
import DashboardPage from "@/pages/DashboardPage";

// Mock the auth context
vi.mock("@/context/AuthContext", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useAuth: vi.fn(),
}));

// Mock API modules used by DashboardPage
vi.mock("@/api/projects", () => ({
  fetchProjects: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/api/sessions", () => ({
  fetchSessions: vi.fn().mockResolvedValue([]),
}));

import { useAuth } from "@/context/AuthContext";

const mockUseAuth = vi.mocked(useAuth);

const authenticatedAuth = {
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
  authEnabled: true,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
};

const unauthenticatedAuth = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  authEnabled: true,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
};

function renderApp(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>
            <Route path="/" element={<DashboardPage />} />
          </Route>
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("App routing with auth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("unauthenticated user navigating to / is redirected to /login", () => {
    mockUseAuth.mockReturnValue(unauthenticatedAuth);
    renderApp("/");
    expect(
      screen.getByRole("heading", { name: /login/i }),
    ).toBeInTheDocument();
  });

  it("unauthenticated user can access /login directly", () => {
    mockUseAuth.mockReturnValue(unauthenticatedAuth);
    renderApp("/login");
    expect(
      screen.getByRole("heading", { name: /login/i }),
    ).toBeInTheDocument();
  });

  it("unauthenticated user can access /register directly", () => {
    mockUseAuth.mockReturnValue(unauthenticatedAuth);
    renderApp("/register");
    expect(
      screen.getByRole("heading", { name: /register/i }),
    ).toBeInTheDocument();
  });

  it("authenticated user navigating to / sees the dashboard", async () => {
    mockUseAuth.mockReturnValue(authenticatedAuth);
    renderApp("/");
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /dashboard/i }),
      ).toBeInTheDocument();
    });
  });

  it("authenticated user sees UserMenu in the layout header", async () => {
    mockUseAuth.mockReturnValue(authenticatedAuth);
    renderApp("/");
    await waitFor(() => {
      expect(screen.getByText("testuser")).toBeInTheDocument();
    });
  });
});
