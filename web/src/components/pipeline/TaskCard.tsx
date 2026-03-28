import type { PipelineTask } from "@/api/pipeline";

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  return `${diffDays}d ago`;
}

const STATUS_COLORS: Record<string, string> = {
  backlog: "bg-gray-600 text-gray-200",
  grooming: "bg-yellow-700 text-yellow-100",
  groomed: "bg-blue-700 text-blue-100",
  implementing: "bg-purple-700 text-purple-100",
  testing: "bg-orange-700 text-orange-100",
  accepting: "bg-teal-700 text-teal-100",
  done: "bg-green-700 text-green-100",
};

interface TaskCardProps {
  task: PipelineTask;
  onClick?: (task: PipelineTask) => void;
}

export default function TaskCard({ task, onClick }: TaskCardProps) {
  const badgeClass =
    STATUS_COLORS[task.pipeline_status] ?? "bg-gray-600 text-gray-200";

  return (
    <button
      type="button"
      data-testid={`task-card-${task.id}`}
      className="w-full text-left bg-gray-800 dark:bg-gray-800 border border-gray-700 rounded-lg p-3 hover:border-gray-500 transition-colors cursor-pointer"
      onClick={() => onClick?.(task)}
    >
      <div className="text-sm font-medium text-gray-100 dark:text-gray-100 mb-2 line-clamp-2">
        {task.title}
      </div>
      <div className="flex items-center justify-between">
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${badgeClass}`}
          data-testid="task-status-badge"
        >
          {task.pipeline_status}
        </span>
        <span
          className="text-xs text-gray-400 dark:text-gray-400"
          data-testid="task-time-ago"
        >
          {timeAgo(task.created_at)}
        </span>
      </div>
    </button>
  );
}

export { timeAgo };
