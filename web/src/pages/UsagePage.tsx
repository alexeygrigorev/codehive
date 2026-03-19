import { useEffect, useState, useCallback } from "react";
import {
  fetchUsage,
  fetchUsageLimits,
  type UsageResponse,
  type UsageRecordRead,
  type UsageSummary,
  type UsageParams,
  type UsageLimitsResponse,
  type RateLimitRead,
  type ModelUsageRead,
} from "@/api/usage";

type TimeRange = "today" | "this_week" | "this_month" | "last_30_days" | "all_time";

function getDateRange(range: TimeRange): { start_date?: string; end_date?: string } {
  const now = new Date();
  const fmt = (d: Date) => d.toISOString().split("T")[0];

  switch (range) {
    case "today":
      return { start_date: fmt(now), end_date: fmt(now) };
    case "this_week": {
      const weekStart = new Date(now);
      weekStart.setDate(now.getDate() - now.getDay());
      return { start_date: fmt(weekStart), end_date: fmt(now) };
    }
    case "this_month": {
      const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
      return { start_date: fmt(monthStart), end_date: fmt(now) };
    }
    case "last_30_days": {
      const past = new Date(now);
      past.setDate(now.getDate() - 30);
      return { start_date: fmt(past), end_date: fmt(now) };
    }
    case "all_time":
      return {};
  }
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(2)}`;
}

function formatResetTime(resetsAt: number): string {
  const now = Math.floor(Date.now() / 1000);
  const diff = resetsAt - now;
  if (diff <= 0) return "resetting soon";

  const hours = Math.floor(diff / 3600);
  const minutes = Math.floor((diff % 3600) / 60);

  if (hours > 24) {
    const resetDate = new Date(resetsAt * 1000);
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const dayName = days[resetDate.getDay()];
    const timeStr = resetDate.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    return `resets ${dayName} ${timeStr}`;
  }

  if (hours > 0) return `resets in ${hours}h ${minutes}m`;
  return `resets in ${minutes}m`;
}

function rateLimitLabel(type: string): string {
  switch (type) {
    case "seven_day":
      return "Weekly";
    case "hourly":
      return "Session";
    case "daily":
      return "Daily";
    default:
      return type;
  }
}

function progressBarColor(utilization: number): string {
  if (utilization > 0.95) return "bg-red-500";
  if (utilization > 0.8) return "bg-amber-500";
  return "bg-green-500";
}

function PlanLimitsSection({ limits }: { limits: UsageLimitsResponse | null }) {
  if (!limits) return null;

  const hasData = limits.rate_limits.length > 0 || limits.model_usage.length > 0;

  return (
    <div className="mb-8" data-testid="plan-limits-section">
      <h2 className="text-lg font-semibold mb-4 dark:text-gray-100">Plan Limits</h2>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="text-base font-medium mb-4 dark:text-gray-200">Claude Code Plan</h3>

        {!hasData && (
          <p className="text-gray-500 dark:text-gray-400" data-testid="plan-limits-empty">
            No plan usage data yet. Run a Claude Code session to see limits.
          </p>
        )}

        {limits.rate_limits.length > 0 && (
          <div className="space-y-4 mb-6">
            {limits.rate_limits.map((rl: RateLimitRead) => (
              <RateLimitBar key={rl.rate_limit_type} rateLimit={rl} />
            ))}
          </div>
        )}

        {limits.model_usage.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
              Per-Model Costs
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="model-usage-table">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 text-left">
                    <th className="px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">
                      Model
                    </th>
                    <th className="px-3 py-2 text-gray-500 dark:text-gray-400 font-medium text-right">
                      Input
                    </th>
                    <th className="px-3 py-2 text-gray-500 dark:text-gray-400 font-medium text-right">
                      Output
                    </th>
                    <th className="px-3 py-2 text-gray-500 dark:text-gray-400 font-medium text-right">
                      Cost
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {limits.model_usage.map((m: ModelUsageRead) => (
                    <tr
                      key={m.model}
                      className="border-b border-gray-100 dark:border-gray-700"
                    >
                      <td className="px-3 py-2 dark:text-gray-300 font-mono text-xs">
                        {m.model}
                      </td>
                      <td className="px-3 py-2 dark:text-gray-300 text-right">
                        {formatTokens(m.input_tokens)}
                      </td>
                      <td className="px-3 py-2 dark:text-gray-300 text-right">
                        {formatTokens(m.output_tokens)}
                      </td>
                      <td className="px-3 py-2 dark:text-gray-300 text-right">
                        {formatCost(m.cost_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RateLimitBar({ rateLimit }: { rateLimit: RateLimitRead }) {
  const pct = Math.round(rateLimit.utilization * 100);
  const color = progressBarColor(rateLimit.utilization);
  const label = rateLimitLabel(rateLimit.rate_limit_type);
  const resetText = formatResetTime(rateLimit.resets_at);

  return (
    <div data-testid={`rate-limit-${rateLimit.rate_limit_type}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium dark:text-gray-200">
          {label}
          {rateLimit.is_using_overage && (
            <span className="ml-2 text-xs text-amber-600 dark:text-amber-400 font-semibold">
              Overage
            </span>
          )}
        </span>
        <span className="text-sm dark:text-gray-300">{pct}% used</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
        <div
          className={`${color} h-2.5 rounded-full transition-all`}
          style={{ width: `${Math.min(pct, 100)}%` }}
          data-testid={`rate-limit-bar-${rateLimit.rate_limit_type}`}
        />
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{resetText}</p>
    </div>
  );
}

export default function UsagePage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("this_month");
  const [data, setData] = useState<UsageResponse | null>(null);
  const [limits, setLimits] = useState<UsageLimitsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const dateRange = getDateRange(timeRange);
      const params: UsageParams = { ...dateRange };
      const [result, limitsResult] = await Promise.all([
        fetchUsage(params),
        fetchUsageLimits(),
      ]);
      setData(result);
      setLimits(limitsResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load usage data");
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh limits every 60 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const limitsResult = await fetchUsageLimits();
        setLimits(limitsResult);
      } catch {
        // Silently ignore refresh errors
      }
    }, 60_000);
    return () => clearInterval(interval);
  }, []);

  const summary: UsageSummary = data?.summary ?? {
    total_requests: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    estimated_cost: 0,
  };

  const records: UsageRecordRead[] = data?.records ?? [];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold dark:text-gray-100">Usage</h1>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value as TimeRange)}
          className="border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-800 dark:text-gray-200"
          data-testid="time-range-select"
        >
          <option value="today">Today</option>
          <option value="this_week">This Week</option>
          <option value="this_month">This Month</option>
          <option value="last_30_days">Last 30 Days</option>
          <option value="all_time">All Time</option>
        </select>
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {/* Plan Limits Section */}
      <PlanLimitsSection limits={limits} />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8" data-testid="summary-cards">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Requests</p>
          <p className="text-2xl font-bold dark:text-gray-100" data-testid="total-requests">
            {loading ? "..." : summary.total_requests.toLocaleString()}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Tokens</p>
          <p className="text-2xl font-bold dark:text-gray-100" data-testid="total-tokens">
            {loading
              ? "..."
              : `${formatTokens(summary.total_input_tokens)} input / ${formatTokens(summary.total_output_tokens)} output`}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">Estimated Cost</p>
          <p className="text-2xl font-bold dark:text-gray-100" data-testid="estimated-cost">
            {loading ? "..." : formatCost(summary.estimated_cost)}
          </p>
        </div>
      </div>

      {/* Usage Records Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-x-auto">
        <table className="w-full text-sm" data-testid="usage-table">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 text-left">
              <th className="px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Date</th>
              <th className="px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Session</th>
              <th className="px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Model</th>
              <th className="px-4 py-3 text-gray-500 dark:text-gray-400 font-medium text-right">
                Input Tokens
              </th>
              <th className="px-4 py-3 text-gray-500 dark:text-gray-400 font-medium text-right">
                Output Tokens
              </th>
              <th className="px-4 py-3 text-gray-500 dark:text-gray-400 font-medium text-right">
                Est. Cost
              </th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && records.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No usage records found for the selected time range.
                </td>
              </tr>
            )}
            {!loading &&
              records.map((record) => (
                <tr
                  key={record.id}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                >
                  <td className="px-4 py-2 dark:text-gray-300">
                    {new Date(record.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 dark:text-gray-300 font-mono text-xs">
                    {record.session_id.substring(0, 8)}...
                  </td>
                  <td className="px-4 py-2 dark:text-gray-300">{record.model}</td>
                  <td className="px-4 py-2 dark:text-gray-300 text-right">
                    {record.input_tokens.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 dark:text-gray-300 text-right">
                    {record.output_tokens.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 dark:text-gray-300 text-right">
                    {formatCost(record.estimated_cost)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
