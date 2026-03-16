import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/api/client";

describe("API client auth integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    // Prevent actual navigation in tests
    Object.defineProperty(window, "location", {
      value: { pathname: "/", href: "/" },
      writable: true,
    });
  });

  it("when codehive_access_token is in localStorage, requests include Authorization: Bearer header", async () => {
    localStorage.setItem("codehive_access_token", "my_token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await apiClient.get("/api/projects");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer my_token",
        }),
      }),
    );
  });

  it("when no token is in localStorage, requests do not include Authorization header", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await apiClient.get("/api/projects");

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const init = call[1] as RequestInit | undefined;
    const headers = (init?.headers as Record<string, string>) ?? {};
    expect(headers.Authorization).toBeUndefined();
  });

  it("on 401 response with a valid refresh token, the client refreshes and retries the request", async () => {
    localStorage.setItem("codehive_access_token", "expired_token");
    localStorage.setItem("codehive_refresh_token", "valid_refresh");

    const fetchMock = vi.spyOn(globalThis, "fetch");

    // First call: 401
    fetchMock.mockResolvedValueOnce(
      new Response("Unauthorized", { status: 401 }),
    );
    // Refresh call: success
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          access_token: "new_token",
          refresh_token: "new_refresh",
        }),
        { status: 200 },
      ),
    );
    // Retry call: success
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ data: "ok" }), { status: 200 }),
    );

    const response = await apiClient.get("/api/projects");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    // Verify refresh was called
    expect(fetchMock.mock.calls[1][0]).toBe(
      "http://localhost:7433/api/auth/refresh",
    );
    // Verify tokens were updated in localStorage
    expect(localStorage.getItem("codehive_access_token")).toBe("new_token");
    expect(localStorage.getItem("codehive_refresh_token")).toBe("new_refresh");
    expect(response.status).toBe(200);
  });

  it("on 401 response with refresh also failing, tokens are cleared", async () => {
    localStorage.setItem("codehive_access_token", "expired_token");
    localStorage.setItem("codehive_refresh_token", "expired_refresh");

    const fetchMock = vi.spyOn(globalThis, "fetch");

    // First call: 401
    fetchMock.mockResolvedValueOnce(
      new Response("Unauthorized", { status: 401 }),
    );
    // Refresh call: also fails
    fetchMock.mockResolvedValueOnce(
      new Response("Unauthorized", { status: 401 }),
    );

    await apiClient.get("/api/projects");

    expect(localStorage.getItem("codehive_access_token")).toBeNull();
    expect(localStorage.getItem("codehive_refresh_token")).toBeNull();
  });
});
