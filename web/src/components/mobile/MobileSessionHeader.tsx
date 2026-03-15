import SessionModeIndicator from "@/components/SessionModeIndicator";

export interface MobileSessionHeaderProps {
  name: string;
  status: string;
  mode: string;
  pendingApprovals: number;
}

const statusColors: Record<string, string> = {
  idle: "bg-gray-100 text-gray-700",
  planning: "bg-yellow-100 text-yellow-800",
  executing: "bg-blue-100 text-blue-800",
  waiting_input: "bg-purple-100 text-purple-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function MobileSessionHeader({
  name,
  status,
  mode,
  pendingApprovals,
}: MobileSessionHeaderProps) {
  const statusClass = statusColors[status] ?? "bg-gray-100 text-gray-700";

  return (
    <div
      className="flex items-center gap-2 border-b border-gray-200 px-3 py-2"
      data-testid="mobile-session-header"
    >
      <h1 className="text-sm font-bold text-gray-900 truncate min-w-0 flex-1">
        {name}
      </h1>
      <span
        className={`session-status inline-flex flex-shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusClass}`}
      >
        {status}
      </span>
      <SessionModeIndicator mode={mode} />
      {pendingApprovals > 0 && (
        <span className="flex-shrink-0 inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
          {pendingApprovals}
        </span>
      )}
    </div>
  );
}
