import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import NewSessionDialog from "@/components/NewSessionDialog";

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
    name: "zai",
    type: "api",
    available: true,
    reason: "",
    models: [
      { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", is_default: true },
      { id: "claude-opus-4-6", name: "Claude Opus 4.6", is_default: false },
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

  it("renders model combobox instead of plain text input", async () => {
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
    expect(screen.getByTestId("model-input")).toBeInTheDocument();
    // The input should have combobox role
    const input = screen.getByTestId("model-input");
    expect(input.getAttribute("role")).toBe("combobox");
  });

  it("loads providers and shows them in dropdown", async () => {
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
    expect(select.options).toHaveLength(3);
  });

  it("default provider is claude with correct model", async () => {
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
    expect(select.value).toBe("claude");

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    expect(modelInput.value).toBe("claude-sonnet-4-6");
  });

  it("selecting Z.ai updates model to claude-sonnet-4-6", async () => {
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

    fireEvent.change(screen.getByTestId("provider-select"), {
      target: { value: "zai" },
    });

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    expect(modelInput.value).toBe("claude-sonnet-4-6");
  });

  it("selecting OpenAI updates model to gpt-5.4", async () => {
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

    fireEvent.change(screen.getByTestId("provider-select"), {
      target: { value: "openai" },
    });

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    expect(modelInput.value).toBe("gpt-5.4");
  });

  it("displays OpenAI label in dropdown", async () => {
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
    const options = Array.from(select.options);
    const openaiOption = options.find((o) => o.value === "openai");
    expect(openaiOption).toBeDefined();
    expect(openaiOption!.textContent).toContain("OpenAI");
  });

  it("calls onSubmit with correct data when form is submitted", async () => {
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

    expect(onSubmit).toHaveBeenCalledWith({
      name: "My ZAI Session",
      provider: "zai",
      model: "claude-sonnet-4-6",
    });
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

  it("shows key status indicator for each provider", async () => {
    const providersWithMissingKey = [
      { ...providers[0] },
      { ...providers[1], available: false, reason: "no key" },
      { ...providers[2] },
    ];
    mockFetchProviders.mockResolvedValue(providersWithMissingKey);

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
    const options = Array.from(select.options);
    // Claude has key set - shows checkmark
    expect(options[0].textContent).toContain("\u2713");
    // Z.ai has no key - shows "(no key)"
    expect(options[1].textContent).toContain("(no key)");
  });

  it("shows model dropdown list when input is focused", async () => {
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

    const modelInput = screen.getByTestId("model-input");
    fireEvent.focus(modelInput);

    await waitFor(() => {
      expect(screen.getByTestId("model-listbox")).toBeInTheDocument();
    });
  });

  it("dropdown shows display names with model IDs", async () => {
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

    const modelInput = screen.getByTestId("model-input");
    fireEvent.focus(modelInput);

    await waitFor(() => {
      expect(screen.getByTestId("model-listbox")).toBeInTheDocument();
    });

    // Should show display name with model ID in parentheses
    const listbox = screen.getByTestId("model-listbox");
    expect(listbox.textContent).toContain("Claude Sonnet 4.6");
    expect(listbox.textContent).toContain("(claude-sonnet-4-6)");
    expect(listbox.textContent).toContain("Claude Opus 4.6");
    expect(listbox.textContent).toContain("(claude-opus-4-6)");
  });

  it("clicking a model option sets the input value to model ID", async () => {
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

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    fireEvent.focus(modelInput);

    await waitFor(() => {
      expect(screen.getByTestId("model-listbox")).toBeInTheDocument();
    });

    // Click on "Claude Opus 4.6"
    const listbox = screen.getByTestId("model-listbox");
    const options = listbox.querySelectorAll('[role="option"]');
    // Second option should be Claude Opus 4.6
    const opusOption = Array.from(options).find((o) =>
      o.textContent?.includes("Claude Opus 4.6"),
    );
    expect(opusOption).toBeDefined();
    fireEvent.mouseDown(opusOption!);

    expect(modelInput.value).toBe("claude-opus-4-6");
  });

  it("user can type a custom model ID freely", async () => {
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

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    fireEvent.change(modelInput, {
      target: { value: "claude-test-model-preview" },
    });

    expect(modelInput.value).toBe("claude-test-model-preview");
  });

  it("form submission sends model ID string not display name", async () => {
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
      expect(screen.getByTestId("model-combobox")).toBeInTheDocument();
    });

    // Select a model from dropdown
    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    fireEvent.focus(modelInput);

    await waitFor(() => {
      expect(screen.getByTestId("model-listbox")).toBeInTheDocument();
    });

    const listbox = screen.getByTestId("model-listbox");
    const options = listbox.querySelectorAll('[role="option"]');
    const opusOption = Array.from(options).find((o) =>
      o.textContent?.includes("Claude Opus 4.6"),
    );
    fireEvent.mouseDown(opusOption!);

    // Submit
    fireEvent.click(screen.getByTestId("create-session-btn"));

    expect(onSubmit).toHaveBeenCalledWith({
      name: "New Session",
      provider: "claude",
      model: "claude-opus-4-6",
    });
  });
});
