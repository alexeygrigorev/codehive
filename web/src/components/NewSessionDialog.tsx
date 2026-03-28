import { useEffect, useState } from "react";
import { fetchProviders, type ProviderInfo } from "@/api/providers";
import ModelCombobox from "@/components/ModelCombobox";

/** Maps provider name to the engine type string used by the backend. */
export const PROVIDER_ENGINE_MAP: Record<string, string> = {
  zai: "native",
  openai: "codex",
  claude: "claude_code",
  codex: "codex_cli",
  copilot: "copilot_cli",
  gemini: "gemini_cli",
};

/** Human-readable labels for each provider. */
const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude",
  codex: "Codex",
  openai: "OpenAI",
  zai: "Z.ai",
  copilot: "Copilot",
  gemini: "Gemini",
};

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: {
    name: string;
    provider: string;
    model: string;
    sub_agent_engines: string[];
  }) => void;
  creating: boolean;
}

function getDefaultModel(provider: ProviderInfo | undefined): string {
  if (!provider) return "";
  const defaultModel = provider.models.find((m) => m.is_default);
  return defaultModel ? defaultModel.id : provider.models[0]?.id ?? "";
}

export default function NewSessionDialog({
  open,
  onClose,
  onSubmit,
  creating,
}: Props) {
  const [name, setName] = useState("New Session");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [model, setModel] = useState("");
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [subAgentEngines, setSubAgentEngines] = useState<Set<string>>(
    new Set(),
  );

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function load() {
      setLoadingProviders(true);
      try {
        const data = await fetchProviders();
        if (cancelled) return;
        setProviders(data);

        // Default orchestrator: first available API provider
        const apiProviders = data.filter((p) => p.type === "api");
        const defaultOrch =
          apiProviders.find((p) => p.available) ?? apiProviders[0];
        if (defaultOrch) {
          setSelectedProvider(defaultOrch.name);
          setModel(getDefaultModel(defaultOrch));
        }

        // Default sub-agent engines: all providers, pre-checked based on availability
        const defaultEngines = new Set<string>();
        for (const p of data) {
          const engine = PROVIDER_ENGINE_MAP[p.name];
          if (engine && p.available) {
            defaultEngines.add(engine);
          }
        }
        setSubAgentEngines(defaultEngines);
      } catch {
        // Silently continue with empty providers list
      } finally {
        if (!cancelled) setLoadingProviders(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [open]);

  function handleProviderChange(providerName: string) {
    setSelectedProvider(providerName);
    const prov = providers.find((p) => p.name === providerName);
    if (prov) {
      setModel(getDefaultModel(prov));
    }
  }

  function handleSubAgentToggle(providerName: string) {
    const engine = PROVIDER_ENGINE_MAP[providerName];
    if (!engine) return;
    setSubAgentEngines((prev) => {
      const next = new Set(prev);
      if (next.has(engine)) {
        next.delete(engine);
      } else {
        next.add(engine);
      }
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      name,
      provider: selectedProvider,
      model,
      sub_agent_engines: Array.from(subAgentEngines),
    });
  }

  if (!open) return null;

  const apiProviders = providers.filter((p) => p.type === "api");
  const currentProvider = providers.find((p) => p.name === selectedProvider);
  const currentModels = currentProvider?.models ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      data-testid="new-session-dialog-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4 p-6"
        data-testid="new-session-dialog"
      >
        <h2 className="text-lg font-semibold mb-4 dark:text-gray-100">
          New Session
        </h2>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            {/* Session name */}
            <div>
              <label
                htmlFor="session-name"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Name
              </label>
              <input
                id="session-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm dark:bg-gray-700 dark:text-gray-100"
                data-testid="session-name-input"
              />
            </div>

            {/* Orchestrator Engine selection */}
            <div>
              <label
                htmlFor="session-provider"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Orchestrator Engine
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                The API-based engine that coordinates work.
              </p>
              {loadingProviders ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Loading providers...
                </p>
              ) : (
                <select
                  id="session-provider"
                  value={selectedProvider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm dark:bg-gray-700 dark:text-gray-100"
                  data-testid="provider-select"
                >
                  {apiProviders.map((p) => {
                    const label = PROVIDER_LABELS[p.name] || p.name;
                    return (
                      <option
                        key={p.name}
                        value={p.name}
                        disabled={!p.available}
                      >
                        {label}
                        {p.available ? "" : ` (${p.reason})`}
                      </option>
                    );
                  })}
                </select>
              )}
            </div>

            {/* Model */}
            <div>
              <label
                htmlFor="session-model"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Model
              </label>
              <ModelCombobox
                models={currentModels}
                value={model}
                onChange={setModel}
              />
            </div>

            {/* Sub-Agent Engines */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Sub-Agent Engines
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Engines the orchestrator may use for coding sub-agents.
              </p>
              <div
                className="space-y-1"
                data-testid="sub-agent-engines"
              >
                {providers.map((p) => {
                  const engine = PROVIDER_ENGINE_MAP[p.name];
                  if (!engine) return null;
                  const label = PROVIDER_LABELS[p.name] || p.name;
                  const checked = subAgentEngines.has(engine);
                  return (
                    <label
                      key={p.name}
                      className={`flex items-center gap-2 text-sm ${
                        !p.available
                          ? "text-gray-400 dark:text-gray-500"
                          : "text-gray-700 dark:text-gray-300"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!p.available}
                        onChange={() => handleSubAgentToggle(p.name)}
                        data-testid={`sub-agent-${p.name}`}
                      />
                      {label}
                      {!p.available && (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          ({p.reason})
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded disabled:opacity-50"
              data-testid="create-session-btn"
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
