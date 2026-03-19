import { Link } from "react-router-dom";

export interface SubAgentEventCardProps {
  eventType: "subagent.spawned" | "subagent.report";
  childName?: string;
  childSessionId?: string;
  engine?: string;
  mission?: string;
  status?: string;
  summary?: string;
  filesChanged?: number;
}

export default function SubAgentEventCard({
  eventType,
  childName,
  childSessionId,
  engine,
  mission,
  status,
  summary,
  filesChanged,
}: SubAgentEventCardProps) {
  const isSpawned = eventType === "subagent.spawned";

  const borderColor = isSpawned
    ? "border-indigo-400"
    : status === "completed"
      ? "border-green-400"
      : status === "failed"
        ? "border-red-400"
        : "border-gray-400";

  const bgColor = isSpawned
    ? "bg-indigo-50 dark:bg-indigo-900/30"
    : status === "completed"
      ? "bg-green-50 dark:bg-green-900/30"
      : status === "failed"
        ? "bg-red-50 dark:bg-red-900/30"
        : "bg-gray-50 dark:bg-gray-800/30";

  const title = isSpawned ? "Spawned sub-agent" : "Sub-agent completed";

  return (
    <div
      className={`subagent-event-card mr-auto max-w-[80%] rounded-lg border-l-4 px-4 py-2 text-sm ${borderColor} ${bgColor}`}
      data-event-type={eventType}
    >
      <div className="font-semibold text-gray-700 dark:text-gray-300">
        {title}:{" "}
        {childSessionId ? (
          <Link
            to={`/sessions/${childSessionId}`}
            className="subagent-card-link text-blue-600 dark:text-blue-400 hover:underline"
          >
            {childName ?? "sub-agent"}
          </Link>
        ) : (
          <span>{childName ?? "sub-agent"}</span>
        )}
        {engine && (
          <span className="subagent-card-engine ml-2 inline-block rounded bg-gray-200 dark:bg-gray-600 px-1.5 py-0.5 text-xs font-medium text-gray-700 dark:text-gray-300">
            {engine}
          </span>
        )}
      </div>
      {isSpawned && mission && (
        <div className="subagent-card-mission mt-1 text-gray-600 dark:text-gray-400">
          Mission: {mission}
        </div>
      )}
      {!isSpawned && summary && (
        <div className="subagent-card-summary mt-1 text-gray-600 dark:text-gray-400">
          {summary}
        </div>
      )}
      {!isSpawned && status && (
        <div className="subagent-card-status mt-1 text-xs text-gray-500 dark:text-gray-400">
          Status: {status}
          {filesChanged !== undefined && `, ${filesChanged} files changed`}
        </div>
      )}
    </div>
  );
}
