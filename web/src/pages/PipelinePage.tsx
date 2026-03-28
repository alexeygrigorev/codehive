import { useState } from "react";
import { usePipelinePolling } from "@/hooks/usePipelinePolling";
import KanbanBoard from "@/components/pipeline/KanbanBoard";
import OrchestratorStatusBar from "@/components/pipeline/OrchestratorStatusBar";
import TaskDetailPanel from "@/components/pipeline/TaskDetailPanel";
import AddTaskModal from "@/components/pipeline/AddTaskModal";
import type { PipelineTask } from "@/api/pipeline";

export default function PipelinePage() {
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    groupedTasks,
    orchestratorStatus,
    loading,
    error,
    refresh,
  } = usePipelinePolling();

  const [selectedTask, setSelectedTask] = useState<PipelineTask | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold dark:text-gray-100">Pipeline</h1>

          {/* Project selector */}
          {projects.length > 0 && (
            <select
              value={selectedProjectId ?? ""}
              onChange={(e) => setSelectedProjectId(e.target.value || null)}
              className="bg-gray-800 text-gray-200 border border-gray-600 rounded px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
              data-testid="pipeline-project-selector"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          disabled={!selectedProjectId}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          data-testid="pipeline-add-task-btn"
        >
          Add Task
        </button>
      </div>

      {/* Orchestrator status */}
      {orchestratorStatus && (
        <div className="mb-4">
          <OrchestratorStatusBar status={orchestratorStatus} />
        </div>
      )}

      {/* Content */}
      {loading && (
        <p className="text-gray-500 dark:text-gray-400">
          Loading pipeline data...
        </p>
      )}

      {error && (
        <p className="text-red-600 dark:text-red-400">{error}</p>
      )}

      {!loading && !error && (
        <KanbanBoard
          groupedTasks={groupedTasks}
          onTaskClick={(task) => setSelectedTask(task)}
        />
      )}

      {/* Task detail panel */}
      {selectedTask && (
        <TaskDetailPanel
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {/* Add task modal */}
      {showAddModal && selectedProjectId && (
        <AddTaskModal
          projectId={selectedProjectId}
          onClose={() => setShowAddModal(false)}
          onTaskAdded={refresh}
        />
      )}
    </div>
  );
}
