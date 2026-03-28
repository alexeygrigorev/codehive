import { useEffect, useState } from "react";
import {
  fetchPromptTemplates,
  updatePromptTemplate,
  resetPromptTemplate,
  fetchEngineConfig,
  updateEngineConfig,
  type PromptTemplate,
  type EngineConfig,
} from "@/api/spawnConfig";

interface ProjectSettingsPanelProps {
  projectId: string;
}

const ENGINE_OPTIONS = ["claude_code", "codex", "codex_cli", "copilot_cli", "gemini_cli"];

function RoleCard({
  template,
  onSave,
  onReset,
}: {
  template: PromptTemplate;
  onSave: (role: string, prompt: string) => Promise<void>;
  onReset: (role: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(template.system_prompt);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(template.system_prompt);
    setEditing(false);
  }, [template.system_prompt]);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(template.role, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    try {
      await onReset(template.role);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
      data-testid={`role-card-${template.role}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
          {template.display_name}
        </h4>
        <span className="text-xs text-gray-500 dark:text-gray-400 uppercase">
          {template.role}
        </span>
        {template.is_custom && (
          <span
            className="inline-flex items-center rounded-full bg-yellow-100 dark:bg-yellow-900 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:text-yellow-200"
            data-testid={`custom-badge-${template.role}`}
          >
            Custom
          </span>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          <textarea
            className="w-full h-32 text-xs font-mono p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            data-testid={`prompt-textarea-${template.role}`}
          />
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              data-testid={`save-prompt-${template.role}`}
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => {
                setEditing(false);
                setDraft(template.system_prompt);
              }}
              className="px-3 py-1 text-xs text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div>
          <pre className="text-xs font-mono bg-gray-50 dark:bg-gray-800 p-2 rounded whitespace-pre-wrap break-words text-gray-600 dark:text-gray-400 mb-2 max-h-24 overflow-auto">
            {template.system_prompt}
          </pre>
          <div className="flex gap-2">
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-1 text-xs text-blue-600 dark:text-blue-400 border border-blue-300 dark:border-blue-600 rounded hover:bg-blue-50 dark:hover:bg-blue-900"
              data-testid={`edit-prompt-${template.role}`}
            >
              Edit
            </button>
            {template.is_custom && (
              <button
                onClick={handleReset}
                disabled={saving}
                className="px-3 py-1 text-xs text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                data-testid={`reset-prompt-${template.role}`}
              >
                Reset to Default
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ProjectSettingsPanel({
  projectId,
}: ProjectSettingsPanelProps) {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [engineConfigs, setEngineConfigs] = useState<EngineConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Engine config form state
  const [selectedEngine, setSelectedEngine] = useState(ENGINE_OPTIONS[0]);
  const [cliFlags, setCliFlags] = useState("");
  const [savingEngine, setSavingEngine] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [tpls, configs] = await Promise.all([
          fetchPromptTemplates(projectId),
          fetchEngineConfig(projectId),
        ]);
        if (cancelled) return;
        setTemplates(tpls);
        setEngineConfigs(configs);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load settings");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [projectId]);

  // Pre-fill CLI flags when selected engine changes
  useEffect(() => {
    const cfg = engineConfigs.find((c) => c.engine === selectedEngine);
    setCliFlags(cfg ? cfg.extra_args.join(" ") : "");
  }, [selectedEngine, engineConfigs]);

  async function handleSaveTemplate(role: string, prompt: string) {
    const updated = await updatePromptTemplate(projectId, role, prompt);
    setTemplates((prev) =>
      prev.map((t) => (t.role === role ? updated : t)),
    );
  }

  async function handleResetTemplate(role: string) {
    const updated = await resetPromptTemplate(projectId, role);
    setTemplates((prev) =>
      prev.map((t) => (t.role === role ? updated : t)),
    );
  }

  async function handleSaveEngine() {
    setSavingEngine(true);
    try {
      const args = cliFlags.trim() ? cliFlags.trim().split(/\s+/) : [];
      const updated = await updateEngineConfig(projectId, selectedEngine, args);
      setEngineConfigs((prev) => {
        const existing = prev.findIndex((c) => c.engine === selectedEngine);
        if (existing >= 0) {
          const copy = [...prev];
          copy[existing] = updated;
          return copy;
        }
        return [...prev, updated];
      });
    } finally {
      setSavingEngine(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-gray-400">Loading settings...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  return (
    <div className="space-y-6" data-testid="project-settings-panel">
      {/* Agent Templates */}
      <div>
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
          Agent Templates
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {templates.map((t) => (
            <RoleCard
              key={t.role}
              template={t}
              onSave={handleSaveTemplate}
              onReset={handleResetTemplate}
            />
          ))}
        </div>
      </div>

      {/* Engine Configuration */}
      <div>
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
          Engine Configuration
        </h3>
        <div
          className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3"
          data-testid="engine-config-section"
        >
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Engine
            </label>
            <select
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value)}
              className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
              data-testid="engine-selector"
            >
              {ENGINE_OPTIONS.map((eng) => (
                <option key={eng} value={eng}>
                  {eng}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Extra CLI Flags
            </label>
            <input
              type="text"
              value={cliFlags}
              onChange={(e) => setCliFlags(e.target.value)}
              placeholder="e.g. --verbose --dangerously-skip-permissions"
              className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
              data-testid="engine-cli-flags"
            />
          </div>
          <button
            onClick={handleSaveEngine}
            disabled={savingEngine}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            data-testid="save-engine-config"
          >
            {savingEngine ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
