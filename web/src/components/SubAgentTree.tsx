import type { SessionRead } from "@/api/sessions";
import SubAgentNode from "./SubAgentNode";

interface SubAgentTreeProps {
  sessions: SessionRead[];
  parentSessionId: string;
}

export default function SubAgentTree({
  sessions,
  parentSessionId,
}: SubAgentTreeProps) {
  // Build tree: direct children of the parent session are roots
  const roots = sessions.filter(
    (s) => s.parent_session_id === parentSessionId,
  );

  // If no sessions match as direct children, treat all sessions as roots
  // (fallback for flat lists where parent_session_id might be null)
  const displayRoots =
    roots.length > 0
      ? roots
      : sessions.filter(
          (s) =>
            s.parent_session_id === null ||
            !sessions.some((other) => other.id === s.parent_session_id),
        );

  return (
    <ul className="space-y-1">
      {displayRoots.map((session) => {
        const children = sessions.filter(
          (s) => s.parent_session_id === session.id,
        );
        return (
          <SubAgentNode
            key={session.id}
            session={session}
            children={children.length > 0 ? children : undefined}
            allSessions={sessions}
          />
        );
      })}
    </ul>
  );
}
