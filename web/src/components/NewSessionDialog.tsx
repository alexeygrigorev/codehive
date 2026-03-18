import { useEffect, useState } from "react";
import { fetchProviders, type ProviderInfo } from "@/api/providers";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: {
    name: string;
    provider: string;
    model: string;
  }) => void;
  creating: boolean;
}

export default function NewSessionDialog({
  open,
  onClose,
  onSubmit,
  creating,
}: Props) {
  const [name, setName] = useState("New Session");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("claude");
  const [model, setModel] = useState("");
  const [loadingProviders, setLoadingProviders] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function load() {
      setLoadingProviders(true);
      try {
        const data = await fetchProviders();
        if (cancelled) return;
        setProviders(data);
        // Set default model from the default provider
        const defaultProv = data.find((p) => p.name === "claude");
        if (defaultProv) {
          setModel(defaultProv.default_model);
        }
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
      setModel(prov.default_model);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({ name, provider: selectedProvider, model });
  }

  if (!open) return null;

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

            {/* Provider selection */}
            <div>
              <label
                htmlFor="session-provider"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Provider
              </label>
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
                  {providers.map((p) => {
                    const labels: Record<string, string> = {
                      claude: "Claude",
                      codex: "Codex",
                      openai: "OpenAI",
                      zai: "Z.ai",
                    };
                    const label = labels[p.name] || p.name;
                    return (
                      <option key={p.name} value={p.name}>
                        {label}
                        {p.available ? " \u2713" : ` (${p.reason})`}
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
              <input
                id="session-model"
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm dark:bg-gray-700 dark:text-gray-100"
                data-testid="model-input"
              />
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
