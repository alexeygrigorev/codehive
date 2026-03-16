import { useEffect, useState } from "react";
import { fetchAgentMessages } from "@/api/agentComm";
import type { AgentCommEvent } from "@/api/agentComm";
import AgentMessageItem from "@/components/AgentMessageItem";

interface AgentCommPanelProps {
  sessionId: string;
}

export default function AgentCommPanel({ sessionId }: AgentCommPanelProps) {
  const [events, setEvents] = useState<AgentCommEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchAgentMessages(sessionId);
        if (!cancelled) {
          setEvents(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to fetch agent messages",
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

  if (loading) {
    return <p className="text-gray-500">Loading agent communications...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (events.length === 0) {
    return <p className="text-gray-500">No agent communications</p>;
  }

  return (
    <div className="space-y-2">
      {events.map((event) => (
        <AgentMessageItem
          key={event.id}
          event={event}
          sessionId={sessionId}
        />
      ))}
    </div>
  );
}
