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
    name: "anthropic",
    base_url: "https://api.anthropic.com",
    api_key_set: true,
    default_model: "claude-sonnet-4-20250514",
  },
  {
    name: "zai",
    base_url: "https://api.z.ai/api/anthropic",
    api_key_set: true,
    default_model: "glm-4.7",
  },
  {
    name: "openai",
    base_url: "https://api.openai.com",
    api_key_set: true,
    default_model: "codex-mini-latest",
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

  it("default provider is anthropic with correct model", async () => {
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
    expect(select.value).toBe("anthropic");

    const modelInput = screen.getByTestId("model-input") as HTMLInputElement;
    expect(modelInput.value).toBe("claude-sonnet-4-20250514");
  });

  it("selecting Z.ai updates model to glm-4.7", async () => {
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
    expect(modelInput.value).toBe("glm-4.7");
  });

  it("selecting OpenAI updates model to codex-mini-latest", async () => {
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
    expect(modelInput.value).toBe("codex-mini-latest");
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
      model: "glm-4.7",
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
      { ...providers[1], api_key_set: false },
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
    // Anthropic has key set - shows checkmark
    expect(options[0].textContent).toContain("\u2713");
    // Z.ai has no key - shows "(no key)"
    expect(options[1].textContent).toContain("(no key)");
  });
});
