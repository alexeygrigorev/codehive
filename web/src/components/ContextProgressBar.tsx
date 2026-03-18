import { useEffect, useState, useCallback } from "react";
import { fetchSessionContext, type ContextUsage } from "@/api/usage";
import { useWebSocketSafe } from "@/context/WebSocketContext";

// ---------- Pure rendering component ----------

export interface ContextProgressBarViewProps {
  usagePercent: number;
  usedTokens: number;
  contextWindow: number;
  estimated?: boolean;
}

/** Pure progress bar -- no data fetching, useful for unit tests. */
export function ContextProgressBarView({
  usagePercent,
  usedTokens,
  contextWindow,
  estimated,
}: ContextProgressBarViewProps) {
  const pct = Math.min(usagePercent, 100);
  const barWidth = Math.max(pct, 0.5); // min visible sliver

  let colorClass: string;
  if (pct >= 80) {
    colorClass = "context-bar-red";
  } else if (pct >= 50) {
    colorClass = "context-bar-yellow";
  } else {
    colorClass = "context-bar-green";
  }

  const tooltipText = `${usedTokens.toLocaleString()} / ${contextWindow.toLocaleString()} tokens (${pct.toFixed(0)}%)${estimated ? " (estimated)" : ""}`;

  return (
    <div
      data-testid="context-progress-bar"
      className="context-progress-bar"
      title={tooltipText}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={tooltipText}
    >
      <div
        className={`context-progress-fill ${colorClass}`}
        style={{ width: `${barWidth}%` }}
      />
    </div>
  );
}

// ---------- Connected component ----------

interface ContextProgressBarProps {
  sessionId: string;
}

/** Thin colour-coded bar showing context window utilisation. */
export default function ContextProgressBar({ sessionId }: ContextProgressBarProps) {
  const [ctx, setCtx] = useState<ContextUsage | null>(null);

  // Returns null if outside WebSocketProvider (safe for tests)
  const ws = useWebSocketSafe();

  const load = useCallback(async () => {
    try {
      const data = await fetchSessionContext(sessionId);
      setCtx(data);
    } catch {
      // Non-critical -- just leave the bar hidden
    }
  }, [sessionId]);

  // Initial fetch
  useEffect(() => {
    load();
  }, [load]);

  // Refresh when new events arrive (message.created, usage.updated, etc.)
  useEffect(() => {
    if (!ws) return;
    const handler = () => {
      load();
    };
    ws.onEvent(handler);
    return () => {
      ws.removeListener(handler);
    };
  }, [ws, load]);

  if (!ctx) return null;

  return (
    <ContextProgressBarView
      usagePercent={ctx.usage_percent}
      usedTokens={ctx.used_tokens}
      contextWindow={ctx.context_window}
      estimated={ctx.estimated}
    />
  );
}
