import { useEffect, useState } from "react";
import { fetchSessionUsage, type UsageSummary } from "@/api/usage";

interface UsagePanelProps {
  sessionId: string;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`;
}

export default function UsagePanel({ sessionId }: UsagePanelProps) {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchSessionUsage(sessionId);
        if (!cancelled) setUsage(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load usage");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();

    // Refresh every 30 seconds
    const interval = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId]);

  if (loading) {
    return <p className="text-sm text-gray-400">Loading usage...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (!usage) {
    return <p className="text-sm text-gray-400">No usage data available.</p>;
  }

  return (
    <div className="space-y-3" data-testid="usage-panel">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Usage</h3>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-gray-50 dark:bg-gray-700 rounded p-2">
          <p className="text-xs text-gray-500 dark:text-gray-400">Input Tokens</p>
          <p className="text-sm font-semibold dark:text-gray-200" data-testid="session-input-tokens">
            {formatTokens(usage.total_input_tokens)}
          </p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700 rounded p-2">
          <p className="text-xs text-gray-500 dark:text-gray-400">Output Tokens</p>
          <p className="text-sm font-semibold dark:text-gray-200" data-testid="session-output-tokens">
            {formatTokens(usage.total_output_tokens)}
          </p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700 rounded p-2">
          <p className="text-xs text-gray-500 dark:text-gray-400">API Requests</p>
          <p className="text-sm font-semibold dark:text-gray-200" data-testid="session-requests">
            {usage.total_requests}
          </p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700 rounded p-2">
          <p className="text-xs text-gray-500 dark:text-gray-400">Est. Cost</p>
          <p className="text-sm font-semibold dark:text-gray-200" data-testid="session-cost">
            {formatCost(usage.estimated_cost)}
          </p>
        </div>
      </div>
    </div>
  );
}
