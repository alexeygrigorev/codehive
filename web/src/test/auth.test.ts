import { describe, it, expect, vi, beforeEach } from "vitest";
import { loginUser, registerUser, refreshToken, getMe } from "@/api/auth";

describe("Auth API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("loginUser calls POST /api/auth/login with email and password and returns parsed JSON", async () => {
    const tokens = {
      access_token: "acc",
      refresh_token: "ref",
      token_type: "bearer",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(tokens), { status: 200 }),
    );

    const result = await loginUser("test@example.com", "password123");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/auth/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "test@example.com", password: "password123" }),
      },
    );
    expect(result).toEqual(tokens);
  });

  it("loginUser throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("Invalid credentials", { status: 401 }),
    );

    await expect(loginUser("bad@example.com", "wrong")).rejects.toThrow(
      "Invalid credentials",
    );
  });

  it("registerUser calls POST /api/auth/register with email, username, password and returns parsed JSON", async () => {
    const tokens = {
      access_token: "acc",
      refresh_token: "ref",
      token_type: "bearer",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(tokens), { status: 201 }),
    );

    const result = await registerUser("test@example.com", "testuser", "pass123");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/auth/register",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "test@example.com",
          username: "testuser",
          password: "pass123",
        }),
      },
    );
    expect(result).toEqual(tokens);
  });

  it("refreshToken calls POST /api/auth/refresh with refresh_token and returns parsed JSON", async () => {
    const tokens = {
      access_token: "new_acc",
      refresh_token: "new_ref",
      token_type: "bearer",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(tokens), { status: 200 }),
    );

    const result = await refreshToken("old_refresh_token");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/auth/refresh",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: "old_refresh_token" }),
      },
    );
    expect(result).toEqual(tokens);
  });

  it("getMe calls GET /api/auth/me with Authorization header and returns user object", async () => {
    const user = {
      id: "u1",
      email: "test@example.com",
      username: "testuser",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), { status: 200 }),
    );

    const result = await getMe("my_token");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/auth/me",
      {
        headers: { Authorization: "Bearer my_token" },
      },
    );
    expect(result).toEqual(user);
  });
});
