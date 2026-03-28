import { useEffect, useState } from "react";
import { apiClient } from "@/api/client";

interface SpawnConfig {
  system_prompt: string;
  initial_message: string;
  engine: string;
  engine_args: string[];
  role: string;
  pipeline_step: string;
}

interface SpawnConfigPanelProps {
  sessionId: string;
}

function CollapsibleSection({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
      <button
        type="button"
        className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
        onClick={() => setOpen(!open)}
        data-testid={`section-toggle-${title.toLowerCase().replace(/\s+/g, "-")}`}
      >
        <span>{title}</span>
        <span className="text-xs text-gray-400">{open ? "collapse" : "expand"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3">
          {children}
        </div>
      )}
    </div>
  );
}

export default function SpawnConfigPanel({ sessionId }: SpawnConfigPanelProps) {
  const [config, setConfig] = useState<SpawnConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const resp = await apiClient.get(`/api/sessions/${sessionId}`);
        if (!resp.ok) throw new Error(`Failed to load session: ${resp.status}`);
        const session = await resp.json();
        const sc = session.config?.spawn_config ?? null;
        if (!cancelled) setConfig(sc);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [sessionId]);

  if (loading) {
    return <p className="text-sm text-gray-400">Loading spawn config...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (!config) {
    return (
      <p className="text-sm text-gray-400" data-testid="spawn-config-empty">
        No spawn configuration recorded for this session
      </p>
    );
  }

  return (
    <div className="space-y-3" data-testid="spawn-config-panel">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Spawn Config</h3>

      <CollapsibleSection title="System Prompt">
        <pre className="text-xs font-mono bg-gray-50 dark:bg-gray-800 p-2 rounded whitespace-pre-wrap break-words text-gray-700 dark:text-gray-300" data-testid="spawn-system-prompt">
          {config.system_prompt}
        </pre>
      </CollapsibleSection>

      <CollapsibleSection title="Initial Message">
        <pre className="text-xs font-mono bg-gray-50 dark:bg-gray-800 p-2 rounded whitespace-pre-wrap break-words text-gray-700 dark:text-gray-300" data-testid="spawn-initial-message">
          {config.initial_message}
        </pre>
      </CollapsibleSection>

      <CollapsibleSection title="Engine Args">
        <div className="text-xs space-y-1" data-testid="spawn-engine-args">
          <p className="text-gray-600 dark:text-gray-400">
            <span className="font-medium">Engine:</span> {config.engine}
          </p>
          <p className="text-gray-600 dark:text-gray-400">
            <span className="font-medium">Role:</span> {config.role}
          </p>
          <p className="text-gray-600 dark:text-gray-400">
            <span className="font-medium">Step:</span> {config.pipeline_step}
          </p>
          {config.engine_args.length > 0 && (
            <p className="text-gray-600 dark:text-gray-400">
              <span className="font-medium">CLI Args:</span>{" "}
              <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">
                {config.engine_args.join(" ")}
              </code>
            </p>
          )}
        </div>
      </CollapsibleSection>
    </div>
  );
}
