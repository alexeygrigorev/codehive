import { useEffect, useState } from "react";
import { fetchEvents } from "@/api/events";
import type { EventRead } from "@/api/events";

interface ActivityPanelProps {
  sessionId: string;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Convert "tool.call.started" to "Tool Call Started" */
function formatEventType(type: string): string {
  return type
    .replace(/[._]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ActivityEntry {
  id: string;
  description: string;
  category: "tool" | "file" | "message" | "other";
  timestamp: string;
  createdAt: string;
}

function buildActivityEntry(event: EventRead): ActivityEntry {
  const timestamp = formatTimestamp(event.created_at);
  const data = event.data ?? {};
  const type = event.type;

  // Tool call events
  if (type.startsWith("tool.call")) {
    const toolName =
      (data.tool as string) ?? (data.name as string) ?? "unknown tool";
    const verb = type.includes("finished") ? "completed" : "called";
    return {
      id: event.id,
      description: `Tool ${verb}: ${toolName}`,
      category: "tool",
      timestamp,
      createdAt: event.created_at,
    };
  }

  // File change events
  if (type === "file.changed" || type === "file_changed") {
    const filePath =
      (data.path as string) ?? (data.file as string) ?? "unknown file";
    return {
      id: event.id,
      description: `File changed: ${filePath}`,
      category: "file",
      timestamp,
      createdAt: event.created_at,
    };
  }

  // Message events
  if (type === "message.created" || type === "message_created") {
    const role = (data.role as string) ?? "unknown";
    return {
      id: event.id,
      description: `Message from ${role}`,
      category: "message",
      timestamp,
      createdAt: event.created_at,
    };
  }

  // Fallback: format the event type into readable text
  return {
    id: event.id,
    description: formatEventType(type),
    category: "other",
    timestamp,
    createdAt: event.created_at,
  };
}

const categoryDotColors: Record<string, string> = {
  tool: "bg-blue-500",
  file: "bg-green-500",
  message: "bg-purple-500",
  other: "bg-gray-400",
};

export default function ActivityPanel({ sessionId }: ActivityPanelProps) {
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
    return <p className="text-gray-500">Loading activity...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (events.length === 0) {
    return <p className="text-gray-500">No activity yet</p>;
  }

  // Most recent events first
  const entries = events.map(buildActivityEntry);
  const sorted = [...entries].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );

  return (
    <ul className="space-y-2" data-testid="activity-list">
      {sorted.map((entry) => (
        <li
          key={entry.id}
          className="flex items-start gap-2 text-sm"
          data-testid="activity-entry"
        >
          <span
            className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${categoryDotColors[entry.category]}`}
            data-testid={`activity-dot-${entry.category}`}
          />
          <div className="min-w-0 flex-1">
            <span className="activity-description">{entry.description}</span>
            <span className="ml-2 text-xs text-gray-400">
              {entry.timestamp}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

// Export for testing
export { buildActivityEntry, formatEventType };
