import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { SessionRead } from "@/api/sessions";
import { fetchSubAgents } from "@/api/subagents";
import RoleBadge from "@/components/RoleBadge";

export interface SessionListProps {
  sessions: SessionRead[];
}

const statusColors: Record<string, string> = {
  idle: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
  planning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  executing: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  waiting_input: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  waiting_approval: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  blocked: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
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
      <p className="text-gray-500 dark:text-gray-400 text-sm">No sessions for this project.</p>
    );
  }

  return (
    <ul className="divide-y divide-gray-200 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
      {sessions.map((session) => {
        const colorClass =
          statusColors[session.status] ?? "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300";
        const subCount = subAgentCounts[session.id] ?? 0;
        return (
          <li key={session.id}>
            <Link
              to={`/sessions/${session.id}`}
              className="block px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {session.agent_avatar_url && (
                    <img
                      src={session.agent_avatar_url}
                      alt={session.agent_name ?? session.name}
                      className="w-8 h-8 rounded-full"
                      data-testid="session-agent-avatar"
                    />
                  )}
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {session.agent_name
                      ? `${session.agent_name} - ${session.name}`
                      : session.name}
                  </span>
                </div>
                <RoleBadge role={session.role} />
                <div className="flex items-center gap-2">
                  {subCount > 0 && (
                    <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-600 dark:text-gray-300">
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
              <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
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
