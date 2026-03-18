import { useState } from "react";
import { Link } from "react-router-dom";
import type { SessionRead } from "@/api/sessions";

const STATUS_COLORS: Record<string, string> = {
  idle: "bg-gray-400",
  planning: "bg-yellow-500",
  executing: "bg-blue-500",
  waiting_input: "bg-purple-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

interface SubAgentNodeProps {
  session: SessionRead;
  children?: SessionRead[];
  allSessions: SessionRead[];
  messageCount?: number;
}

export default function SubAgentNode({
  session,
  children,
  allSessions,
  messageCount,
}: SubAgentNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = children !== undefined && children.length > 0;

  return (
    <li className="sub-agent-node">
      <div className="flex items-center gap-2 rounded border border-gray-200 dark:border-gray-700 px-2 py-1.5 text-sm">
        {hasChildren ? (
          <button
            type="button"
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            onClick={() => setExpanded((prev) => !prev)}
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? "\u25BE" : "\u25B8"}
          </button>
        ) : (
          <span className="inline-block w-4" />
        )}
        <span
          className={`sub-agent-status inline-block h-2.5 w-2.5 rounded-full ${STATUS_COLORS[session.status] ?? "bg-gray-400"}`}
          title={session.status}
          data-status={session.status}
        />
        <Link
          to={`/sessions/${session.id}`}
          className="sub-agent-link flex-1 text-blue-600 dark:text-blue-400 hover:underline"
        >
          {session.name}
        </Link>
        {messageCount !== undefined && messageCount > 0 && (
          <span className="message-count-badge inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-xs text-white">
            {messageCount}
          </span>
        )}
        <span className="text-xs text-gray-400">{session.status}</span>
      </div>
      {hasChildren && expanded && (
        <ul className="ml-4 mt-1 space-y-1">
          {children.map((child) => {
            const grandchildren = allSessions.filter(
              (s) => s.parent_session_id === child.id,
            );
            return (
              <SubAgentNode
                key={child.id}
                session={child}
                children={grandchildren.length > 0 ? grandchildren : undefined}
                allSessions={allSessions}
              />
            );
          })}
        </ul>
      )}
    </li>
  );
}
