import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchRoles,
  createRole,
  updateRole,
  deleteRole,
} from "@/api/roles";

describe("API: roles", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchRoles calls GET /api/roles and returns parsed JSON", async () => {
    const mockData = [
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
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchRoles();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/roles",
    );
    expect(result).toEqual(mockData);
  });

  it("createRole calls POST /api/roles with body", async () => {
    const body = {
      name: "custom-role",
      display_name: "Custom Role",
      description: "A custom role",
    };
    const mockResponse = { ...body, is_builtin: false, responsibilities: [], allowed_tools: [], denied_tools: [], coding_rules: [], system_prompt_extra: "" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await createRole(body);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/roles",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    expect(result).toEqual(mockResponse);
  });

  it("updateRole calls PUT /api/roles/{name} with body", async () => {
    const body = { display_name: "Updated Name" };
    const mockResponse = {
      name: "my-role",
      display_name: "Updated Name",
      description: "",
      is_builtin: false,
      responsibilities: [],
      allowed_tools: [],
      denied_tools: [],
      coding_rules: [],
      system_prompt_extra: "",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await updateRole("my-role", body);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/roles/my-role",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    expect(result).toEqual(mockResponse);
  });

  it("deleteRole calls DELETE /api/roles/{name}", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );

    await deleteRole("my-role");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/roles/my-role",
      {
        method: "DELETE",
      },
    );
  });

  it("fetchRoles throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchRoles()).rejects.toThrow("Failed to fetch roles: 500");
  });
});
