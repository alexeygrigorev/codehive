import { useEffect, useState } from "react";
import { fetchTasks } from "@/api/tasks";
import type { TaskRead } from "@/api/tasks";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-400",
  running: "bg-blue-500",
  done: "bg-green-500",
  failed: "bg-red-500",
  blocked: "bg-yellow-500",
  skipped: "bg-gray-300",
};

interface TodoPanelProps {
  sessionId: string;
}

export default function TodoPanel({ sessionId }: TodoPanelProps) {
  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchTasks(sessionId);
        if (!cancelled) {
          setTasks(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to fetch tasks",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (loading) {
    return <p className="text-gray-500">Loading tasks...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (tasks.length === 0) {
    return <p className="text-gray-500">No tasks yet</p>;
  }

  const doneCount = tasks.filter((t) => t.status === "done").length;

  return (
    <div>
      <p className="mb-2 text-sm font-medium text-gray-700">
        {doneCount}/{tasks.length} done
      </p>
      <ul className="space-y-2">
        {tasks.map((task) => (
          <li
            key={task.id}
            className="flex items-center gap-2 rounded border border-gray-200 px-2 py-1.5 text-sm"
          >
            <span
              className={`task-status-indicator inline-block h-2.5 w-2.5 rounded-full ${STATUS_COLORS[task.status] ?? "bg-gray-400"}`}
              title={task.status}
              data-status={task.status}
            />
            <span className="flex-1">{task.title}</span>
            <span className="text-xs text-gray-400">{task.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
