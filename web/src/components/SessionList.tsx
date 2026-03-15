import { Link } from "react-router-dom";
import type { SessionRead } from "@/api/sessions";

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

export default function SessionList({ sessions }: SessionListProps) {
  if (sessions.length === 0) {
    return (
      <p className="text-gray-500 text-sm">No sessions for this project.</p>
    );
  }

  return (
    <ul className="divide-y divide-gray-200 border border-gray-200 rounded-lg bg-white">
      {sessions.map((session) => {
        const colorClass = statusColors[session.status] ?? "bg-gray-100 text-gray-700";
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
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
                >
                  {session.status}
                </span>
              </div>
              <div className="mt-1 text-xs text-gray-500">
                <span>Mode: {session.mode}</span>
                <span className="mx-2">|</span>
                <span>Engine: {session.engine}</span>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
