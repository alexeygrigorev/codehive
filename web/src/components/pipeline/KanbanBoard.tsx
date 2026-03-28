import type { PipelineTask } from "@/api/pipeline";
import { PIPELINE_COLUMNS, type GroupedTasks } from "@/hooks/usePipelinePolling";
import KanbanColumn from "./KanbanColumn";

interface KanbanBoardProps {
  groupedTasks: GroupedTasks;
  onTaskClick?: (task: PipelineTask) => void;
}

export default function KanbanBoard({
  groupedTasks,
  onTaskClick,
}: KanbanBoardProps) {
  return (
    <div
      data-testid="kanban-board"
      className="flex gap-4 overflow-x-auto pb-4 min-h-[300px]"
    >
      {PIPELINE_COLUMNS.map((col) => (
        <KanbanColumn
          key={col.status}
          label={col.label}
          status={col.status}
          tasks={groupedTasks[col.status] ?? []}
          onTaskClick={onTaskClick}
        />
      ))}
    </div>
  );
}
