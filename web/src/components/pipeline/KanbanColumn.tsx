import type { PipelineTask } from "@/api/pipeline";
import TaskCard from "./TaskCard";

interface KanbanColumnProps {
  label: string;
  status: string;
  tasks: PipelineTask[];
  onTaskClick?: (task: PipelineTask) => void;
}

export default function KanbanColumn({
  label,
  status,
  tasks,
  onTaskClick,
}: KanbanColumnProps) {
  return (
    <div
      data-testid={`kanban-column-${status}`}
      className="flex-shrink-0 w-72 flex flex-col bg-gray-900 dark:bg-gray-900 rounded-lg"
    >
      {/* Column header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-gray-200 dark:text-gray-200">
          {label}
        </h3>
        <span
          className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full"
          data-testid={`column-count-${status}`}
        >
          {tasks.length}
        </span>
      </div>

      {/* Card list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[100px]">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onClick={onTaskClick} />
        ))}
      </div>
    </div>
  );
}
