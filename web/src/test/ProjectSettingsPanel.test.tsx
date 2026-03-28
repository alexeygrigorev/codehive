import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/spawnConfig", () => ({
  fetchPromptTemplates: vi.fn(),
  updatePromptTemplate: vi.fn(),
  resetPromptTemplate: vi.fn(),
  fetchEngineConfig: vi.fn(),
  updateEngineConfig: vi.fn(),
}));

import {
  fetchPromptTemplates,
  updatePromptTemplate,
  resetPromptTemplate,
  fetchEngineConfig,
  updateEngineConfig,
} from "@/api/spawnConfig";
import ProjectSettingsPanel from "@/components/ProjectSettingsPanel";

const mockFetchTemplates = vi.mocked(fetchPromptTemplates);
const mockUpdateTemplate = vi.mocked(updatePromptTemplate);
const mockResetTemplate = vi.mocked(resetPromptTemplate);
const mockFetchEngineConfig = vi.mocked(fetchEngineConfig);
const mockUpdateEngineConfig = vi.mocked(updateEngineConfig);

const DEFAULT_TEMPLATES = [
  { role: "pm", display_name: "Product Manager", system_prompt: "PM prompt", is_custom: false },
  { role: "swe", display_name: "Software Engineer", system_prompt: "SWE prompt", is_custom: false },
  { role: "qa", display_name: "QA Tester", system_prompt: "QA prompt", is_custom: false },
  { role: "oncall", display_name: "On-Call Engineer", system_prompt: "OnCall prompt", is_custom: false },
];

describe("ProjectSettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchTemplates.mockResolvedValue(DEFAULT_TEMPLATES);
    mockFetchEngineConfig.mockResolvedValue([]);
  });

  it("renders four role cards", async () => {
    render(<ProjectSettingsPanel projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByTestId("project-settings-panel")).toBeInTheDocument();
    });

    expect(screen.getByTestId("role-card-pm")).toBeInTheDocument();
    expect(screen.getByTestId("role-card-swe")).toBeInTheDocument();
    expect(screen.getByTestId("role-card-qa")).toBeInTheDocument();
    expect(screen.getByTestId("role-card-oncall")).toBeInTheDocument();
  });

  it("shows Custom badge for custom templates", async () => {
    mockFetchTemplates.mockResolvedValue([
      ...DEFAULT_TEMPLATES.slice(0, 1),
      { role: "swe", display_name: "Software Engineer", system_prompt: "Custom", is_custom: true },
      ...DEFAULT_TEMPLATES.slice(2),
    ]);

    render(<ProjectSettingsPanel projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByTestId("custom-badge-swe")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("custom-badge-pm")).not.toBeInTheDocument();
  });

  it("clicking Edit shows textarea, Save updates template", async () => {
    const user = userEvent.setup();
    mockUpdateTemplate.mockResolvedValue({
      role: "swe",
      display_name: "Software Engineer",
      system_prompt: "New custom prompt",
      is_custom: true,
    });

    render(<ProjectSettingsPanel projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByTestId("edit-prompt-swe")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("edit-prompt-swe"));

    const textarea = screen.getByTestId("prompt-textarea-swe");
    expect(textarea).toBeInTheDocument();

    await user.clear(textarea);
    await user.type(textarea, "New custom prompt");
    await user.click(screen.getByTestId("save-prompt-swe"));

    await waitFor(() => {
      expect(mockUpdateTemplate).toHaveBeenCalledWith("p1", "swe", "New custom prompt");
    });
  });

  it("clicking Reset to Default resets template", async () => {
    mockFetchTemplates.mockResolvedValue([
      ...DEFAULT_TEMPLATES.slice(0, 1),
      { role: "swe", display_name: "Software Engineer", system_prompt: "Custom", is_custom: true },
      ...DEFAULT_TEMPLATES.slice(2),
    ]);
    mockResetTemplate.mockResolvedValue({
      role: "swe",
      display_name: "Software Engineer",
      system_prompt: "SWE prompt",
      is_custom: false,
    });

    const user = userEvent.setup();
    render(<ProjectSettingsPanel projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByTestId("reset-prompt-swe")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("reset-prompt-swe"));

    await waitFor(() => {
      expect(mockResetTemplate).toHaveBeenCalledWith("p1", "swe");
    });
  });

  it("renders engine config section", async () => {
    render(<ProjectSettingsPanel projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByTestId("engine-config-section")).toBeInTheDocument();
    });

    expect(screen.getByTestId("engine-selector")).toBeInTheDocument();
    expect(screen.getByTestId("engine-cli-flags")).toBeInTheDocument();
    expect(screen.getByTestId("save-engine-config")).toBeInTheDocument();
  });

  it("saves engine config", async () => {
    const user = userEvent.setup();
    mockUpdateEngineConfig.mockResolvedValue({
      engine: "claude_code",
      extra_args: ["--verbose"],
    });

    render(<ProjectSettingsPanel projectId="p1" />);

    await waitFor(() => {
      expect(screen.getByTestId("engine-cli-flags")).toBeInTheDocument();
    });

    const input = screen.getByTestId("engine-cli-flags");
    await user.type(input, "--verbose");
    await user.click(screen.getByTestId("save-engine-config"));

    await waitFor(() => {
      expect(mockUpdateEngineConfig).toHaveBeenCalledWith(
        "p1",
        "claude_code",
        ["--verbose"],
      );
    });
  });

  it("shows loading state", () => {
    mockFetchTemplates.mockReturnValue(new Promise(() => {}));
    mockFetchEngineConfig.mockReturnValue(new Promise(() => {}));

    render(<ProjectSettingsPanel projectId="p1" />);
    expect(screen.getByText("Loading settings...")).toBeInTheDocument();
  });
});
