import { useCallback, useEffect, useRef, useState } from "react";
import { updateSession, type SessionRead } from "@/api/sessions";
import { apiClient } from "@/api/client";
import { fetchEventsByType, type EventRead } from "@/api/events";

interface CompactionPanelProps {
  sessionId: string;
  session?: SessionRead | null;
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

export default function CompactionPanel({
  sessionId,
  session: sessionProp,
}: CompactionPanelProps) {
  const [fetchedSession, setFetchedSession] = useState<SessionRead | null>(
    null,
  );
  const session = sessionProp ?? fetchedSession;
  const config = session?.config ?? {};
  const [enabled, setEnabled] = useState<boolean>(
    (config.compaction_enabled as boolean) ?? true,
  );
  const [threshold, setThreshold] = useState<number>(
    (config.compaction_threshold as number) ?? 0.8,
  );
  const [keepRecent, setKeepRecent] = useState<number>(
    (config.compaction_preserve_last_n as number) ?? 4,
  );
  const [history, setHistory] = useState<EventRead[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch session data if not provided via props
  useEffect(() => {
    if (sessionProp) return;
    let cancelled = false;
    async function loadSession() {
      try {
        const resp = await apiClient.get(`/api/sessions/${sessionId}`);
        if (resp.ok && !cancelled) {
          const data = (await resp.json()) as SessionRead;
          setFetchedSession(data);
        }
      } catch {
        // Silently ignore fetch errors
      }
    }
    loadSession();
    return () => {
      cancelled = true;
    };
  }, [sessionId, sessionProp]);

  // Sync state when session prop changes
  useEffect(() => {
    const cfg = session?.config ?? {};
    setEnabled((cfg.compaction_enabled as boolean) ?? true);
    setThreshold((cfg.compaction_threshold as number) ?? 0.8);
    setKeepRecent((cfg.compaction_preserve_last_n as number) ?? 4);
  }, [session]);

  // Load compaction history
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const events = await fetchEventsByType(
          sessionId,
          "context.compacted",
        );
        if (!cancelled) {
          setHistory(events.reverse());
        }
      } catch {
        // Silently ignore fetch errors for history
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const saveConfig = useCallback(
    (patch: Record<string, unknown>) => {
      const currentConfig = session?.config ?? {};
      updateSession(sessionId, {
        config: { ...currentConfig, ...patch },
      }).catch(() => {
        // Silently ignore save errors
      });
    },
    [sessionId, session],
  );

  const debouncedSave = useCallback(
    (patch: Record<string, unknown>) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => saveConfig(patch), 500);
    },
    [saveConfig],
  );

  const handleToggle = useCallback(() => {
    const newVal = !enabled;
    setEnabled(newVal);
    saveConfig({ compaction_enabled: newVal });
  }, [enabled, saveConfig]);

  const handleThreshold = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      setThreshold(val);
      debouncedSave({ compaction_threshold: val });
    },
    [debouncedSave],
  );

  const handleKeepRecentChange = useCallback(
    (delta: number) => {
      const newVal = Math.min(10, Math.max(2, keepRecent + delta));
      setKeepRecent(newVal);
      debouncedSave({ compaction_preserve_last_n: newVal });
    },
    [keepRecent, debouncedSave],
  );

  return (
    <div className="space-y-4" data-testid="compaction-panel">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
        Compaction Settings
      </h3>

      {/* Auto-compaction toggle */}
      <div className="flex items-center justify-between">
        <label
          htmlFor="compaction-toggle"
          className="text-sm text-gray-600 dark:text-gray-400"
        >
          Auto-compaction
        </label>
        <button
          id="compaction-toggle"
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={handleToggle}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            enabled
              ? "bg-blue-600"
              : "bg-gray-300 dark:bg-gray-600"
          }`}
          data-testid="compaction-toggle"
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>

      {/* Threshold slider */}
      <div>
        <label
          htmlFor="compaction-threshold"
          className="text-sm text-gray-600 dark:text-gray-400"
        >
          Threshold:{" "}
          <span data-testid="threshold-value">
            {Math.round(threshold * 100)}%
          </span>
        </label>
        <input
          id="compaction-threshold"
          type="range"
          min="0.50"
          max="0.95"
          step="0.01"
          value={threshold}
          onChange={handleThreshold}
          className="mt-1 w-full"
          data-testid="compaction-threshold"
        />
      </div>

      {/* Keep recent stepper */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-600 dark:text-gray-400">
          Keep recent messages
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleKeepRecentChange(-1)}
            disabled={keepRecent <= 2}
            className="rounded bg-gray-200 px-2 py-1 text-sm dark:bg-gray-600 disabled:opacity-50"
            data-testid="keep-recent-minus"
          >
            -
          </button>
          <span
            className="text-sm font-medium dark:text-gray-200"
            data-testid="keep-recent-value"
          >
            {keepRecent}
          </span>
          <button
            type="button"
            onClick={() => handleKeepRecentChange(1)}
            disabled={keepRecent >= 10}
            className="rounded bg-gray-200 px-2 py-1 text-sm dark:bg-gray-600 disabled:opacity-50"
            data-testid="keep-recent-plus"
          >
            +
          </button>
        </div>
      </div>

      {/* Compaction History */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mt-4 mb-2">
          Compaction History
        </h3>
        {loading && (
          <p className="text-sm text-gray-400">Loading history...</p>
        )}
        {!loading && history.length === 0 && (
          <p className="text-sm text-gray-400" data-testid="no-history">
            No compactions yet.
          </p>
        )}
        {history.map((event) => {
          const data = event.data;
          const isExpanded = expandedId === event.id;
          return (
            <div
              key={event.id}
              className="mb-2 rounded border border-gray-200 dark:border-gray-700 p-2 cursor-pointer"
              data-testid="compaction-history-entry"
              onClick={() => setExpandedId(isExpanded ? null : event.id)}
            >
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">
                  {formatRelativeTime(event.created_at)}
                </span>
                <span className="text-gray-700 dark:text-gray-300">
                  {String(data.messages_compacted ?? 0)} compacted
                </span>
              </div>
              {!isExpanded && data.summary_text && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {truncate(String(data.summary_text), 80)}
                </p>
              )}
              {isExpanded && (
                <div
                  className="mt-2 text-xs text-gray-600 dark:text-gray-400 space-y-1"
                  data-testid="compaction-history-expanded"
                >
                  <p>
                    Timestamp: {new Date(event.created_at).toLocaleString()}
                  </p>
                  <p>Messages compacted: {String(data.messages_compacted)}</p>
                  <p>Messages preserved: {String(data.messages_preserved)}</p>
                  <p>
                    Threshold: {String(data.threshold_percent ?? "N/A")}%
                  </p>
                  {data.summary_text && (
                    <p className="whitespace-pre-wrap">
                      Summary: {String(data.summary_text)}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
