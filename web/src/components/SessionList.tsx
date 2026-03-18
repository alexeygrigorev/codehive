import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { SessionRead } from "@/api/sessions";
import { fetchSubAgents } from "@/api/subagents";

export interface SessionListProps {
  sessions: SessionRead[];
}

const statusColors: Record<string, string> = {
  idle: "bg-gray-100 text-gray-700",
  planning: "bg-yellow-100 text-yellow-800",
  executing: "bg-blue-100 text-blue-800",
  waiting_input: "bg-purple-100 text-purple-800",
  waiting_approval: "bg-purple-100 text-purple-800",
  blocked: "bg-red-100 text-red-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export default function SessionList({ sessions }: SessionListProps) {
  const [subAgentCounts, setSubAgentCounts] = useState<Record<string, number>>(
    {},
  );

  useEffect(() => {
    let cancelled = false;
    async function loadCounts() {
      const counts: Record<string, number> = {};
      await Promise.all(
        sessions.map(async (s) => {
          try {
            const subs = await fetchSubAgents(s.id);
            counts[s.id] = subs.length;
          } catch {
            counts[s.id] = 0;
          }
        }),
      );
      if (!cancelled) setSubAgentCounts(counts);
    }
    if (sessions.length > 0) loadCounts();
    return () => {
      cancelled = true;
    };
  }, [sessions]);

  if (sessions.length === 0) {
    return (
      <p className="text-gray-500 text-sm">No sessions for this project.</p>
    );
  }

  return (
    <ul className="divide-y divide-gray-200 border border-gray-200 rounded-lg bg-white">
      {sessions.map((session) => {
        const colorClass =
          statusColors[session.status] ?? "bg-gray-100 text-gray-700";
        const subCount = subAgentCounts[session.id] ?? 0;
        return (
          <li key={session.id}>
            <Link
              to={`/sessions/${session.id}`}
              className="block px-4 py-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">
                  {session.name}
                </span>
                <div className="flex items-center gap-2">
                  {subCount > 0 && (
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                      {subCount} sub-agent{subCount !== 1 ? "s" : ""}
                    </span>
                  )}
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
                  >
                    {session.status}
                  </span>
                </div>
              </div>
              <div className="mt-1 text-xs text-gray-500">
                <span>Mode: {session.mode}</span>
                <span className="mx-2">|</span>
                <span>Engine: {session.engine}</span>
                <span className="mx-2">|</span>
                <span>{formatRelativeTime(session.created_at)}</span>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
