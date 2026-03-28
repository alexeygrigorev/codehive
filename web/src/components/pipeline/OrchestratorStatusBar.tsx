import type { OrchestratorStatus } from "@/api/pipeline";

interface OrchestratorStatusBarProps {
  status: OrchestratorStatus;
}

export default function OrchestratorStatusBar({
  status,
}: OrchestratorStatusBarProps) {
  const isRunning = status.status === "running";
  const flaggedCount = status.flagged_tasks?.length ?? 0;
  const batchCount = status.current_batch?.length ?? 0;
  const activeCount = status.active_sessions?.length ?? 0;

  return (
    <div
      data-testid="orchestrator-status-bar"
      className={`flex items-center gap-4 px-4 py-2 rounded-lg border text-sm ${
        isRunning
          ? "bg-green-900/30 border-green-700 text-green-300"
          : "bg-gray-800 border-gray-700 text-gray-400"
      }`}
    >
      {/* Status indicator */}
      <div className="flex items-center gap-2">
        <span
          data-testid="orchestrator-status-dot"
          className={`inline-block w-2 h-2 rounded-full ${
            isRunning ? "bg-green-400" : "bg-gray-500"
          }`}
        />
        <span data-testid="orchestrator-status-text" className="font-medium">
          Orchestrator: {isRunning ? "Running" : "Stopped"}
        </span>
      </div>

      {/* Batch info */}
      <span className="text-xs">
        Batch: {batchCount} task{batchCount !== 1 ? "s" : ""}
      </span>

      {/* Active sessions */}
      <span className="text-xs">
        Sessions: {activeCount}
      </span>

      {/* Flagged tasks warning */}
      {flaggedCount > 0 && (
        <span
          data-testid="orchestrator-flagged-warning"
          className="text-xs text-yellow-400 font-medium"
        >
          {flaggedCount} flagged
        </span>
      )}
    </div>
  );
}
