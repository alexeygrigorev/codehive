import { useEffect, useState } from "react";
import { fetchEvents } from "@/api/events";
import type { EventRead } from "@/api/events";

interface TimelinePanelProps {
  sessionId: string;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function TimelinePanel({ sessionId }: TimelinePanelProps) {
  const [events, setEvents] = useState<EventRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchEvents(sessionId);
        if (!cancelled) {
          setEvents(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to fetch events",
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
    return <p className="text-gray-500 dark:text-gray-400">Loading timeline...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (events.length === 0) {
    return <p className="text-gray-500 dark:text-gray-400">No events yet</p>;
  }

  return (
    <ul className="space-y-2">
      {events.map((event) => (
        <li
          key={event.id}
          className="flex items-start gap-2 border-l-2 border-gray-300 dark:border-gray-600 pl-3 text-sm"
        >
          <div>
            <span className="font-medium">{event.type}</span>
            <span className="ml-2 text-xs text-gray-400">
              {formatTimestamp(event.created_at)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
