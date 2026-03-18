import type { AgentCommEvent } from "@/api/agentComm";

interface AgentMessageItemProps {
  event: AgentCommEvent;
  sessionId: string;
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function AgentMessageItem({
  event,
  sessionId,
}: AgentMessageItemProps) {
  const isOutgoing = event.data.sender_session_id === sessionId;
  const isQuery = event.type === "agent.query";

  const alignmentClass = isOutgoing
    ? "ml-auto bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100"
    : "mr-auto bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100";

  const queryClass = isQuery ? "border-l-4 border-yellow-400" : "";

  return (
    <div
      className={`agent-message-item max-w-[80%] rounded-lg px-4 py-2 ${alignmentClass} ${queryClass}`}
      data-type={event.type}
    >
      <div className="mb-1 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span className="font-medium">
          {isOutgoing ? "To" : "From"}:{" "}
          {isOutgoing
            ? event.data.target_session_id
            : event.data.sender_session_id}
        </span>
        {isQuery && (
          <span className="agent-query-label rounded bg-yellow-200 dark:bg-yellow-800 px-1 text-yellow-800 dark:text-yellow-200">
            query
          </span>
        )}
        <span className="agent-message-time">
          {formatTimestamp(event.data.timestamp)}
        </span>
      </div>
      <p className="whitespace-pre-wrap">{event.data.message}</p>
    </div>
  );
}
