import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import NewSessionDialog from "@/components/NewSessionDialog";
import { PROVIDER_ENGINE_MAP } from "@/components/NewSessionDialog";

vi.mock("@/api/providers", () => ({
  fetchProviders: vi.fn(),
}));

import { fetchProviders } from "@/api/providers";
const mockFetchProviders = vi.mocked(fetchProviders);

const providers = [
  {
    name: "claude",
    type: "cli",
    available: true,
    reason: "",
    models: [
      { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", is_default: true },
      { id: "claude-opus-4-6", name: "Claude Opus 4.6", is_default: false },
      { id: "claude-sonnet-4-5", name: "Claude Sonnet 4.5", is_default: false },
      { id: "claude-haiku-4-5", name: "Claude Haiku 4.5", is_default: false },
    ],
  },
  {
    name: "codex",
    type: "cli",
    available: true,
    reason: "",
    models: [
      { id: "gpt-5.4", name: "GPT-5.4", is_default: true },
    ],
  },
  {
    name: "openai",
    type: "api",
    available: true,
    reason: "",
    models: [
      { id: "gpt-5.4", name: "GPT-5.4", is_default: true },
      { id: "gpt-5.4-mini", name: "GPT-5.4 Mini", is_default: false },
      { id: "o4-mini", name: "O4 Mini", is_default: false },
      { id: "o3", name: "O3", is_default: false },
    ],
  },
  {
    name: "zai",
    type: "api",
    available: true,
    reason: "",
    models: [
      { id: "glm-5", name: "GLM-5", is_default: true },
      { id: "glm-5-turbo", name: "GLM-5 Turbo", is_default: false },
      { id: "glm-4.7", name: "GLM-4.7", is_default: false },
    ],
  },
  {
    name: "copilot",
    type: "cli",
    available: false,
    reason: "CLI not found",
    models: [{ id: "default", name: "Default", is_default: true }],
  },
];

describe("NewSessionDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchProviders.mockResolvedValue(providers);
  });

  it("renders nothing when not open", () => {
    render(
      <NewSessionDialog
        open={false}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );
    expect(screen.queryByTestId("new-session-dialog")).not.toBeInTheDocument();
  });

  it("renders dialog when open", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("new-session-dialog")).toBeInTheDocument();
    });
    expect(screen.getByText("New Session")).toBeInTheDocument();
    expect(screen.getByTestId("session-name-input")).toBeInTheDocument();
    expect(screen.getByTestId("model-input")).toBeInTheDocument();
  });

  it("orchestrator dropdown shows ONLY API providers", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("provider-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    // Should only have 2 options: openai and zai (API providers)
    expect(select.options).toHaveLength(2);
    const optionValues = Array.from(select.options).map((o) => o.value);
    expect(optionValues).toContain("openai");
    expect(optionValues).toContain("zai");
    // CLI providers should NOT be in the dropdown
    expect(optionValues).not.toContain("claude");
    expect(optionValues).not.toContain("codex");
    expect(optionValues).not.toContain("copilot");
  });

  it("default orchestrator is first available API provider", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("provider-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    // zai is preferred as default orchestrator when available
    expect(select.value).toBe("zai");

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    expect(modelInput.value).toBe("glm-5");
  });

  it("sub-agent checkboxes show ALL providers", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("sub-agent-engines")).toBeInTheDocument();
    });

    // All 5 providers should have checkboxes
    expect(screen.getByTestId("sub-agent-claude")).toBeInTheDocument();
    expect(screen.getByTestId("sub-agent-codex")).toBeInTheDocument();
    expect(screen.getByTestId("sub-agent-openai")).toBeInTheDocument();
    expect(screen.getByTestId("sub-agent-zai")).toBeInTheDocument();
    expect(screen.getByTestId("sub-agent-copilot")).toBeInTheDocument();
  });

  it("available sub-agents are pre-checked, unavailable are unchecked and disabled", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("sub-agent-engines")).toBeInTheDocument();
    });

    // Only Claude and Codex are pre-checked by default
    expect(screen.getByTestId("sub-agent-claude")).toBeChecked();
    expect(screen.getByTestId("sub-agent-codex")).toBeChecked();

    // Other available providers are NOT pre-checked
    expect(screen.getByTestId("sub-agent-openai")).not.toBeChecked();
    expect(screen.getByTestId("sub-agent-zai")).not.toBeChecked();

    // Unavailable provider should be unchecked and disabled
    const copilotCheckbox = screen.getByTestId("sub-agent-copilot") as HTMLInputElement;
    expect(copilotCheckbox).not.toBeChecked();
    expect(copilotCheckbox).toBeDisabled();
  });

  it("unavailable API provider shown disabled in orchestrator dropdown", async () => {
    const withUnavailableApi = providers.map((p) =>
      p.name === "openai"
        ? { ...p, available: false, reason: "API key not set" }
        : p,
    );
    mockFetchProviders.mockResolvedValue(withUnavailableApi);

    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("provider-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    const openaiOption = Array.from(select.options).find(
      (o) => o.value === "openai",
    );
    expect(openaiOption).toBeDefined();
    expect(openaiOption!.disabled).toBe(true);
    expect(openaiOption!.textContent).toContain("API key not set");

    // Z.ai should be auto-selected as the only available API provider
    expect(select.value).toBe("zai");
  });

  it("selecting orchestrator provider updates model dropdown", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("provider-select")).toBeInTheDocument();
    });

    // Default is zai with glm-5
    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    expect(modelInput.value).toBe("glm-5");

    // Switch to openai — model should update to gpt-5.4
    fireEvent.change(screen.getByTestId("provider-select"), {
      target: { value: "openai" },
    });
    expect(modelInput.value).toBe("gpt-5.4");
  });

  it("calls onSubmit with provider, model, and sub_agent_engines", async () => {
    const onSubmit = vi.fn();
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={onSubmit}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("provider-select")).toBeInTheDocument();
    });

    // Select Z.ai
    fireEvent.change(screen.getByTestId("provider-select"), {
      target: { value: "zai" },
    });

    // Change name
    fireEvent.change(screen.getByTestId("session-name-input"), {
      target: { value: "My ZAI Session" },
    });

    // Submit
    fireEvent.click(screen.getByTestId("create-session-btn"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "My ZAI Session",
        provider: "zai",
        model: "glm-5",
      }),
    );
    // sub_agent_engines should be an array of engine strings
    const callArgs = onSubmit.mock.calls[0][0];
    expect(callArgs.sub_agent_engines).toBeInstanceOf(Array);
    expect(callArgs.sub_agent_engines.length).toBeGreaterThan(0);
  });

  it("unchecking a sub-agent engine removes it from submit data", async () => {
    const onSubmit = vi.fn();
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={onSubmit}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("sub-agent-engines")).toBeInTheDocument();
    });

    // Uncheck claude
    fireEvent.click(screen.getByTestId("sub-agent-claude"));

    // Submit
    fireEvent.click(screen.getByTestId("create-session-btn"));

    const callArgs = onSubmit.mock.calls[0][0];
    expect(callArgs.sub_agent_engines).not.toContain("claude_code");
  });

  it("Create button is disabled when creating", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={true}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("create-session-btn")).toBeInTheDocument();
    });

    expect(screen.getByTestId("create-session-btn")).toBeDisabled();
    expect(screen.getByTestId("create-session-btn")).toHaveTextContent(
      "Creating...",
    );
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = vi.fn();
    render(
      <NewSessionDialog
        open={true}
        onClose={onClose}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows Orchestrator Engine label", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Orchestrator Engine")).toBeInTheDocument();
    });
    expect(screen.getByText("Sub-Agent Engines")).toBeInTheDocument();
  });

  it("renders model combobox", async () => {
    render(
      <NewSessionDialog
        open={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        creating={false}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("model-combobox")).toBeInTheDocument();
    });
    const input = screen.getByTestId("model-input");
    expect(input.getAttribute("role")).toBe("combobox");
  });
});

describe("PROVIDER_ENGINE_MAP", () => {
  it("maps zai to native", () => {
    expect(PROVIDER_ENGINE_MAP["zai"]).toBe("native");
  });

  it("maps openai to codex", () => {
    expect(PROVIDER_ENGINE_MAP["openai"]).toBe("codex");
  });

  it("maps claude to claude_code", () => {
    expect(PROVIDER_ENGINE_MAP["claude"]).toBe("claude_code");
  });

  it("maps codex to codex_cli", () => {
    expect(PROVIDER_ENGINE_MAP["codex"]).toBe("codex_cli");
  });

  it("maps copilot to copilot_cli", () => {
    expect(PROVIDER_ENGINE_MAP["copilot"]).toBe("copilot_cli");
  });

  it("maps gemini to gemini_cli", () => {
    expect(PROVIDER_ENGINE_MAP["gemini"]).toBe("gemini_cli");
  });
});
