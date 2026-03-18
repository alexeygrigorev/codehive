import type { EventRead } from "@/api/events";

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Convert "tool.call.started" to "Tool Call Started" */
export function formatEventType(type: string): string {
  return type
    .replace(/[._]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export interface ActivityEntry {
  id: string;
  description: string;
  category: "tool" | "file" | "message" | "other";
  timestamp: string;
  createdAt: string;
}

export function buildActivityEntry(event: EventRead): ActivityEntry {
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
