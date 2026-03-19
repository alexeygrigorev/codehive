import { useEffect, useState, useCallback } from "react";
import { fetchSubAgents } from "@/api/subagents";
import type { SessionRead } from "@/api/sessions";
import { useWebSocketSafe } from "@/context/WebSocketContext";
import type { EventCallback } from "@/api/websocket";
import AggregatedProgress from "@/components/AggregatedProgress";
import SubAgentTree from "@/components/SubAgentTree";

interface SubAgentPanelProps {
  sessionId: string;
}

export default function SubAgentPanel({ sessionId }: SubAgentPanelProps) {
  const [subAgents, setSubAgents] = useState<SessionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const ws = useWebSocketSafe();

  const reload = useCallback(async () => {
    try {
      const data = await fetchSubAgents(sessionId);
      setSubAgents(data);
    } catch {
      // Silently ignore reload failures -- initial load handles errors
    }
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSubAgents(sessionId);
        if (!cancelled) {
          setSubAgents(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to fetch sub-agents",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Listen for subagent.spawned events to auto-refresh the list
  useEffect(() => {
    if (!ws) return;

    const handleEvent: EventCallback = (event) => {
      if (
        event.type === "subagent.spawned" ||
        event.type === "subagent.report"
      ) {
        reload();
      }
    };

    ws.onEvent(handleEvent);
    return () => {
      ws.removeListener(handleEvent);
    };
  }, [ws, reload]);

  if (loading) {
    return <p className="text-gray-500 dark:text-gray-400">Loading sub-agents...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (subAgents.length === 0) {
    return <p className="text-gray-500 dark:text-gray-400">No sub-agents</p>;
  }

  const completedCount = subAgents.filter(
    (s) => s.status === "completed",
  ).length;

  return (
    <div>
      <AggregatedProgress total={subAgents.length} completed={completedCount} />
      <SubAgentTree sessions={subAgents} parentSessionId={sessionId} />
    </div>
  );
}
